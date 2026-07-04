from datetime import date
from decimal import Decimal

from pipeline.models import TransactionRecord
from pipeline.oracle_client import CHECKSUM_QUERY_SQL, MERGE_TRANSACTION_SQL, OracleClient


class FakeCursor:
    def __init__(self, fetchall_result=None) -> None:
        self.execute_calls = []
        self.executemany_calls = []
        self._fetchall_result = fetchall_result or []

    def execute(self, statement, parameters=None):
        self.execute_calls.append((statement, parameters))

    def executemany(self, statement, parameters):
        self.executemany_calls.append((statement, parameters))

    def fetchall(self):
        return self._fetchall_result


class FakeConnection:
    def __init__(self, fetchall_result=None) -> None:
        self.cursor_obj = FakeCursor(fetchall_result)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1


def _record(
    transaction_id="TXN-000001", account_id="ACCT-123456", amount="12.34"
) -> TransactionRecord:
    return TransactionRecord(
        transaction_id=transaction_id,
        account_id=account_id,
        txn_type="CREDIT",
        amount=Decimal(amount),
        txn_date=date(2026, 1, 15),
        line_number=1,
    )


def test_upsert_transactions_uses_merge_via_executemany_and_commits_once() -> None:
    connection = FakeConnection()
    client = OracleClient(connection)
    record = _record()

    count = client.upsert_transactions([record], load_run_id="run-1")

    assert count == 1
    assert connection.commits == 1
    # Batched via executemany, not one execute() call per record.
    assert connection.cursor_obj.execute_calls == []
    assert len(connection.cursor_obj.executemany_calls) == 1
    statement, params_list = connection.cursor_obj.executemany_calls[0]
    assert statement == MERGE_TRANSACTION_SQL
    assert params_list[0]["transaction_id"] == "TXN-000001"
    assert params_list[0]["load_run_id"] == "run-1"


def test_upsert_transactions_splits_into_batches() -> None:
    connection = FakeConnection()
    client = OracleClient(connection)
    records = [_record(transaction_id=f"TXN-{i:06d}") for i in range(5)]

    count = client.upsert_transactions(records, load_run_id="run-1", batch_size=2)

    assert count == 5
    assert connection.commits == 1  # still a single commit for the whole load
    # 5 records at batch_size=2 -> batches of 2, 2, 1
    batch_sizes = [len(params) for _, params in connection.cursor_obj.executemany_calls]
    assert batch_sizes == [2, 2, 1]


def test_reconcile_source_totals() -> None:
    client = OracleClient(FakeConnection())

    assert client.reconcile_source_totals(
        source_count=2,
        source_amount_total=Decimal("10.00"),
        target_count=2,
        target_amount_total=Decimal("10.00"),
    )
    assert not client.reconcile_source_totals(
        source_count=2,
        source_amount_total=Decimal("10.00"),
        target_count=1,
        target_amount_total=Decimal("10.00"),
    )


def test_reconcile_row_level_matches_when_checksums_align() -> None:
    record = _record()
    # Must match _checksum()'s formatting: id|account|type|amount(.2f)|isoformat date
    matching_row = ("TXN-000001|ACCT-123456|CREDIT|12.34|2026-01-15",)
    connection = FakeConnection(fetchall_result=[matching_row])
    client = OracleClient(connection)

    result = client.reconcile_row_level(source_records=[record], load_run_id="run-1")

    assert result.matched is True
    assert result.missing_in_target == frozenset()
    assert result.unexpected_in_target == frozenset()
    # Confirms the checksum query actually ran with the right bind param.
    statement, params = connection.cursor_obj.execute_calls[0]
    assert statement == CHECKSUM_QUERY_SQL
    assert params == {"load_run_id": "run-1"}


def test_reconcile_row_level_detects_swapped_amounts() -> None:
    # Same count and same total sum, but a different row-level distribution
    # — exactly what reconcile_source_totals (count/sum only) would miss.
    source_records = [_record(transaction_id="TXN-000001", amount="100.00")]
    mismatched_row = ("TXN-000001|ACCT-123456|CREDIT|999.00|2026-01-15",)
    connection = FakeConnection(fetchall_result=[mismatched_row])
    client = OracleClient(connection)

    result = client.reconcile_row_level(source_records=source_records, load_run_id="run-1")

    assert result.matched is False
    assert "TXN-000001|ACCT-123456|CREDIT|100.00|2026-01-15" in result.missing_in_target
    assert "TXN-000001|ACCT-123456|CREDIT|999.00|2026-01-15" in result.unexpected_in_target
