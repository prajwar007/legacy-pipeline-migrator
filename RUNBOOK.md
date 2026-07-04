# 3am Failure Runbook

## First Triage

1. Check the Airflow task that failed and capture `dag_id`, `run_id`, `task_id`, source file name, and exception.
2. Check application logs. The default local file is `logs/pipeline.log` when using `config/logging.yaml`.
3. Check for an alert in the configured Slack channel (see "Alerting" below) — it carries the same task/run_id/error as the log line.
4. Confirm whether the failure happened before or after Oracle load started.

## Reproducing Locally

To reproduce an Oracle- or SFTP-related failure against real infrastructure
rather than guessing from logs alone:

```bash
cp .env.example .env
docker compose up -d oracle sftp
source .env && export ORACLE_USER ORACLE_PASSWORD ORACLE_DSN
pytest -m integration -v
```

See "Local Integration Testing" in `README.md` for details.

## Alerting

Task failures trigger `_log_failure` (see `dags/transaction_pipeline_dag.py`), which does two things:

- Logs a structured error line (lands in `logs/pipeline.log`).
- Posts to a Slack-compatible incoming webhook via `pipeline.alerting.send_alert`, if `ALERT_WEBHOOK_URL` is set in the environment. If it's not set, this is a silent no-op — the pipeline still runs and logs, it just doesn't page anyone. Confirm `ALERT_WEBHOOK_URL` is actually configured in the deployment environment if alerts seem to be missing.
- The webhook call has a 5-second timeout and never raises — a broken alert channel will show up as an error in `logs/pipeline.log` (`Failed to send alert webhook: ...`), not as a second pipeline failure.

## Common Failures

### SFTP File Missing Marker

Symptom: sensor waits or fails because `transactions.txt.done` is absent.

Action:

- Verify the producer finished uploading the data file.
- Confirm the marker file has the same base name with `.done` appended.
- Do not process the data file manually while upload is still in progress.

### Validation Errors

Symptom: records are rejected for invalid account id, type, amount, date, or malformed field count.

Action:

- Review `load_errors` if the run reached the database.
- Compare the rejected line against `config/field_mapping.yaml`.
- Ask the upstream owner to resend corrected records, or quarantine the bad file and rerun with the corrected file.

### Oracle Load Failure

Symptom: database connection, merge, or commit failure.

Action:

- Confirm database availability and credentials.
- Check whether any records were committed.
- Rerun the same file after the issue is fixed. The merge is designed to be idempotent using `transaction_id`.

### Reconciliation Mismatch

Symptom: source count/checksum differs from target count/checksum.

Action:

- Stop downstream publication.
- Run `sql/reconciliation_queries.sql` for the affected `load_run_id`.
- Compare parser output count with database rows.
- Rerun after identifying missing or mismatched records.

## Recovery Rule

Prefer rerunning the pipeline with the same immutable source file. The loader and Oracle merge path are designed so reruns do not duplicate transactions.

