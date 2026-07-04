from __future__ import annotations

import uuid

import pytest

from pipeline.loader import load_transaction_file
from pipeline.oracle_client import OracleClient

pytestmark = pytest.mark.integration


@pytest.fixture
def oracle_client(oracle_connection) -> OracleClient:
    return OracleClient(oracle_connection)


def _load_run_id() -> str:
    # Unique per test invocation so tests can run repeatedly without
    # colliding with rows from a previous run that _clean_tables missed.
    return f"itest-{uuid.uuid4().hex[:12]}"


def _insert_load_run(oracle_connection, load_run_id: str, source_file: str) -> None:
    cursor = oracle_connection.cursor()
    cursor.execute(
        """
        INSERT INTO load_runs (load_run_id, source_file, status)
        VALUES (:load_run_id, :source_file, 'RUNNING')
        """,
        {"load_run_id": load_run_id, "source_file": source_file},
    )
    oracle_connection.commit()


def test_upsert_transactions_against_real_oracle(oracle_connection, oracle_client) -> None:
    load_run_id = _load_run_id()
    _insert_load_run(oracle_connection, load_run_id, "tests/fixtures/valid_transactions.txt")

    result = load_transaction_file("tests/fixtures/valid_transactions.txt")
    assert result.rejected_count == 0, result.errors

    loaded_count = oracle_client.upsert_transactions(result.records, load_run_id=load_run_id)

    assert loaded_count == len(result.records)

    cursor = oracle_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE load_run_id = :id", {"id": load_run_id})
    (row_count,) = cursor.fetchone()
    assert row_count == len(result.records)


def test_upsert_is_idempotent_on_rerun(oracle_connection, oracle_client) -> None:
    # This is the single most important thing to prove about this pipeline:
    # running the same load twice must not create duplicate rows.
    load_run_id = _load_run_id()
    _insert_load_run(oracle_connection, load_run_id, "tests/fixtures/valid_transactions.txt")

    result = load_transaction_file("tests/fixtures/valid_transactions.txt")

    first_count = oracle_client.upsert_transactions(result.records, load_run_id=load_run_id)
    second_count = oracle_client.upsert_transactions(result.records, load_run_id=load_run_id)

    assert first_count == second_count == len(result.records)

    cursor = oracle_connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM transactions WHERE load_run_id = :id", {"id": load_run_id})
    (row_count,) = cursor.fetchone()
    # Not double the row count — MERGE updated the existing rows in place.
    assert row_count == len(result.records)


def test_reconcile_row_level_matches_after_real_load(oracle_connection, oracle_client) -> None:
    load_run_id = _load_run_id()
    _insert_load_run(oracle_connection, load_run_id, "tests/fixtures/valid_transactions.txt")

    result = load_transaction_file("tests/fixtures/valid_transactions.txt")
    oracle_client.upsert_transactions(result.records, load_run_id=load_run_id)

    reconciliation = oracle_client.reconcile_row_level(
        source_records=result.records, load_run_id=load_run_id
    )

    assert reconciliation.matched is True
    assert reconciliation.missing_in_target == frozenset()
    assert reconciliation.unexpected_in_target == frozenset()


def test_reconcile_row_level_detects_real_drift(oracle_connection, oracle_client) -> None:
    # Loads valid data, then directly mutates one row in Oracle to simulate
    # drift (e.g. a manual hotfix or a bug in a different loader) — proves
    # reconcile_row_level would actually catch that in production, not just
    # against mocks.
    load_run_id = _load_run_id()
    _insert_load_run(oracle_connection, load_run_id, "tests/fixtures/valid_transactions.txt")

    result = load_transaction_file("tests/fixtures/valid_transactions.txt")
    oracle_client.upsert_transactions(result.records, load_run_id=load_run_id)

    cursor = oracle_connection.cursor()
    first_transaction_id = result.records[0].transaction_id
    cursor.execute(
        "UPDATE transactions SET amount = amount + 1 WHERE transaction_id = :id",
        {"id": first_transaction_id},
    )
    oracle_connection.commit()

    reconciliation = oracle_client.reconcile_row_level(
        source_records=result.records, load_run_id=load_run_id
    )

    assert reconciliation.matched is False
    assert len(reconciliation.missing_in_target) == 1
    assert len(reconciliation.unexpected_in_target) == 1
