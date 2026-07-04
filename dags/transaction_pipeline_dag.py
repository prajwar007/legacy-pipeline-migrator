from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger("pipeline.dag")

SOURCE_FILENAME = "transactions.txt"
LOCAL_DOWNLOAD_DIR = "/tmp/transaction_pipeline"
THRESHOLDS_CONFIG_PATH = "config/thresholds.yaml"
FIELD_MAPPING_CONFIG_PATH = "config/field_mapping.yaml"


def _log_failure(context: dict) -> None:
    task_instance = context.get("task_instance")
    task_id = getattr(task_instance, "task_id", "unknown")
    dag_run = context.get("dag_run")
    run_id = getattr(dag_run, "run_id", "unknown")
    exception = context.get("exception")

    message = f"transaction pipeline failed task={task_id} run_id={run_id} error={exception}"

    # Structured log entry lands in the same stream configured in
    # config/logging.yaml, for post-hoc debugging via RUNBOOK.md.
    logger.error(message)

    # Best-effort alert to a Slack-compatible webhook (see alerting.py and
    # ALERT_WEBHOOK_URL in RUNBOOK.md). This is separate from the log line
    # above on purpose: logs are for someone debugging after the fact,
    # this is for someone who needs to know *right now*. send_alert()
    # never raises, so a misconfigured or unreachable webhook can't turn
    # one failure into two.
    from pipeline.alerting import send_alert

    send_alert(message)


def _build_sftp_client():
    from pipeline.sftp_client import SftpClient, SftpConfig

    config = SftpConfig(
        host=os.environ["SFTP_HOST"],
        port=int(os.environ.get("SFTP_PORT", "22")),
        username=os.environ["SFTP_USERNAME"],
        password=os.environ["SFTP_PASSWORD"],
        remote_dir=os.environ.get("SFTP_REMOTE_DIR", "/incoming"),
    )
    return SftpClient(config)


def _build_oracle_client():
    from pipeline.oracle_client import OracleClient, connect

    connection = connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
    )
    return OracleClient(connection)


def _load_validated_file(local_path: str):
    from pipeline.config import load_field_mapping, load_thresholds
    from pipeline.loader import load_transaction_file

    thresholds = load_thresholds(THRESHOLDS_CONFIG_PATH)
    field_mapping = load_field_mapping(FIELD_MAPPING_CONFIG_PATH)
    return load_transaction_file(
        local_path,
        large_debit_threshold=thresholds.large_debit_threshold,
        field_mapping=field_mapping,
    )


try:
    from airflow.decorators import dag, task
except ImportError:
    dag = None
    task = None


if dag and task:

    @dag(
        dag_id="transaction_pipeline",
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        default_args={
            "retries": 2,
            "retry_delay": timedelta(minutes=5),
            "on_failure_callback": _log_failure,
        },
        tags=["migration", "transactions"],
    )
    def transaction_pipeline():
        @task(retries=3, retry_delay=timedelta(minutes=1))
        def wait_for_marker() -> str:
            # SFTP connectivity/availability is transient — retrying here
            # is genuinely useful, unlike retrying a deterministic
            # validation failure below.
            client = _build_sftp_client()
            ready = client.poll_for_ready_file(
                SOURCE_FILENAME, timeout_seconds=300, interval_seconds=10
            )
            if not ready:
                raise TimeoutError(f"{SOURCE_FILENAME} marker not found within timeout")

            local_path = f"{LOCAL_DOWNLOAD_DIR}/{SOURCE_FILENAME}"
            client.download(SOURCE_FILENAME, local_path)
            return local_path

        @task(retries=0)
        # Intentionally no retries: a rejected-record count is a
        # deterministic outcome of the file's contents, not a transient
        # fault. Retrying would just fail identically three more times
        # and delay the alert — the RUNBOOK.md "Validation Errors" section
        # is the correct next step, not an automatic retry.
        def validate_file(local_path: str) -> dict:
            result = _load_validated_file(local_path)
            if result.rejected_count:
                raise ValueError(f"{result.rejected_count} rejected records in {local_path}")
            return {"local_path": local_path, "accepted": result.accepted_count}

        @task(retries=3, retry_delay=timedelta(minutes=2))
        def load_to_oracle(validated: dict) -> dict:
            # Re-parses the already-validated file rather than passing
            # TransactionRecord objects through XCom. This is deliberate:
            # XCom values are serialized (JSON by default), so pushing a
            # list of dataclasses with Decimal/date fields through it adds
            # custom-serialization complexity for no real benefit — each
            # task should be independently re-runnable from small,
            # JSON-safe inputs (here, just a file path) rather than
            # depending on another task's in-memory Python objects.
            result = _load_validated_file(validated["local_path"])

            oracle_client = _build_oracle_client()
            # transaction_id is the true idempotency key (see the MERGE in
            # oracle_client.py) — load_run_id is only an audit/tracking
            # column, so it doesn't need to be identical across retries,
            # just unique enough to identify this run in load_errors/
            # load_runs. A production version would prefer Airflow's own
            # run_id (via get_current_context()) for that.
            load_run_id = f"{SOURCE_FILENAME}-{datetime.utcnow():%Y%m%dT%H%M%S}"
            loaded_count = oracle_client.upsert_transactions(
                result.records, load_run_id=load_run_id
            )
            return {"loaded": loaded_count, "load_run_id": load_run_id}

        load_to_oracle(validate_file(wait_for_marker()))

    transaction_pipeline()
