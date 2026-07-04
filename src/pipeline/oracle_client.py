from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from pipeline.models import ReconciliationResult, TransactionRecord


class CursorLike(Protocol):
    def execute(self, statement: str, parameters: dict[str, Any] | None = None) -> Any: ...
    def executemany(self, statement: str, parameters: list[dict[str, Any]]) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class ConnectionLike(Protocol):
    def cursor(self) -> CursorLike: ...
    def commit(self) -> None: ...


MERGE_TRANSACTION_SQL = """
MERGE INTO transactions tgt
USING (
    SELECT :transaction_id AS transaction_id,
           :account_id AS account_id,
           :txn_type AS txn_type,
           :amount AS amount,
           :txn_date AS txn_date,
           :load_run_id AS load_run_id
    FROM dual
) src
ON (tgt.transaction_id = src.transaction_id)
WHEN MATCHED THEN UPDATE SET
    tgt.account_id = src.account_id,
    tgt.txn_type = src.txn_type,
    tgt.amount = src.amount,
    tgt.txn_date = src.txn_date,
    tgt.load_run_id = src.load_run_id,
    tgt.updated_at = SYSTIMESTAMP
WHEN NOT MATCHED THEN INSERT (
    transaction_id, account_id, txn_type, amount, txn_date, load_run_id
) VALUES (
    src.transaction_id, src.account_id, src.txn_type, src.amount, src.txn_date, src.load_run_id
)
"""

# Kept in sync with sql/reconciliation_queries.sql. Amount and date are
# explicitly formatted with TO_CHAR rather than relying on implicit
# to-string conversion, which is governed by session NLS settings
# (NLS_NUMERIC_CHARACTERS, NLS_DATE_FORMAT) and can silently drift from
# how Python formats the same value — a classic source of false-positive
# reconciliation mismatches.
CHECKSUM_QUERY_SQL = """
SELECT transaction_id || '|' || account_id || '|' || txn_type || '|' ||
       TO_CHAR(amount, 'FM999999999990.00') || '|' ||
       TO_CHAR(txn_date, 'YYYY-MM-DD') AS checksum_input
FROM transactions
WHERE load_run_id = :load_run_id
ORDER BY transaction_id
"""

DEFAULT_BATCH_SIZE = 500


@dataclass
class OracleClient:
    connection: ConnectionLike

    def upsert_transactions(
        self,
        records: Iterable[TransactionRecord],
        *,
        load_run_id: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> int:
        # Batched via executemany/array-bind rather than one execute() per
        # row — row-by-row execution is the classic cause of a load that
        # used to take minutes suddenly taking an hour once volume grows.
        cursor = self.connection.cursor()
        count = 0
        batch: list[dict[str, Any]] = []

        for record in records:
            batch.append(_record_params(record, load_run_id))
            if len(batch) >= batch_size:
                cursor.executemany(MERGE_TRANSACTION_SQL, batch)
                count += len(batch)
                batch = []

        if batch:
            cursor.executemany(MERGE_TRANSACTION_SQL, batch)
            count += len(batch)

        self.connection.commit()
        return count

    def reconcile_source_totals(
        self,
        *,
        source_count: int,
        source_amount_total: Decimal,
        target_count: int,
        target_amount_total: Decimal,
    ) -> bool:
        return source_count == target_count and source_amount_total == target_amount_total

    def fetch_target_checksums(self, *, load_run_id: str) -> set[str]:
        cursor = self.connection.cursor()
        cursor.execute(CHECKSUM_QUERY_SQL, {"load_run_id": load_run_id})
        return {row[0] for row in cursor.fetchall()}

    def reconcile_row_level(
        self,
        *,
        source_records: Iterable[TransactionRecord],
        load_run_id: str,
    ) -> ReconciliationResult:
        # Row-count and sum-total matching (reconcile_source_totals) can't
        # catch a same-count/same-sum-but-wrong-records case — e.g. two
        # accounts' amounts swapped. Comparing per-row checksums closes
        # that gap.
        source_checksums = {_checksum(record) for record in source_records}
        target_checksums = self.fetch_target_checksums(load_run_id=load_run_id)

        return ReconciliationResult(
            matched=source_checksums == target_checksums,
            missing_in_target=frozenset(source_checksums - target_checksums),
            unexpected_in_target=frozenset(target_checksums - source_checksums),
        )


def connect(user: str, password: str, dsn: str) -> ConnectionLike:
    import oracledb

    return oracledb.connect(user=user, password=password, dsn=dsn)


def _record_params(record: TransactionRecord, load_run_id: str) -> dict[str, Any]:
    return {
        "transaction_id": record.transaction_id,
        "account_id": record.account_id,
        "txn_type": record.txn_type,
        "amount": record.amount,
        "txn_date": record.txn_date,
        "load_run_id": load_run_id,
    }


def _checksum(record: TransactionRecord) -> str:
    # Must match CHECKSUM_QUERY_SQL's TO_CHAR formatting exactly.
    return (
        f"{record.transaction_id}|{record.account_id}|{record.txn_type}|"
        f"{record.amount:.2f}|{record.txn_date.isoformat()}"
    )
