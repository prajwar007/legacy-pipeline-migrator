from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipeline.oracle_client import connect

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"

# ORA-00955: name is already used by an existing object
# ORA-02275: such a referential constraint already exists in the table
ALREADY_EXISTS_ORA_CODES = ("ORA-00955", "ORA-02275")


def _oracle_env_configured() -> bool:
    return all(os.environ.get(var) for var in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN"))


@pytest.fixture(scope="session")
def oracle_connection():
    if not _oracle_env_configured():
        pytest.skip(
            "ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN not set — start the "
            "containers with `docker compose up -d oracle` and export the "
            "vars from .env.example (or copy it to .env and source it) "
            "before running `pytest -m integration`."
        )

    connection = connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
    )
    _apply_schema(connection)
    yield connection
    connection.close()


def _apply_schema(connection) -> None:
    statements = [
        stmt.strip()
        for stmt in SCHEMA_PATH.read_text(encoding="utf-8").split(";")
        if stmt.strip()
    ]
    cursor = connection.cursor()
    for statement in statements:
        try:
            cursor.execute(statement)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see below
            # Makes repeated local test runs idempotent without needing a
            # separate teardown/DROP step: if the table already exists
            # from a prior run, that's fine, keep going.
            if not any(code in str(exc) for code in ALREADY_EXISTS_ORA_CODES):
                raise
    connection.commit()


@pytest.fixture(autouse=True)
def _clean_tables(oracle_connection):
    # Runs before and after every integration test so tests don't leak
    # rows into each other via shared PRIMARY KEY values across runs.
    _truncate_all(oracle_connection)
    yield
    _truncate_all(oracle_connection)


def _truncate_all(connection) -> None:
    cursor = connection.cursor()
    # Child-to-parent order, matching the FK dependencies in schema.sql.
    for table in ("load_errors", "transactions", "load_runs"):
        cursor.execute(f"DELETE FROM {table}")  # noqa: S608 - fixed table list, not user input
    connection.commit()
