from pipeline.models import LoadError, RawTransactionRecord
from pipeline.parse import parse_line, parse_lines


def test_parse_valid_line() -> None:
    parsed = parse_line("TXN-000001|ACCT-123456|DEBIT|42.50|2026-01-15", 1)

    assert isinstance(parsed, RawTransactionRecord)
    assert parsed.transaction_id == "TXN-000001"
    assert parsed.txn_type == "DEBIT"


def test_parse_rejects_extra_delimiter() -> None:
    parsed = parse_line("TXN-000001|ACCT-123456|DEBIT|42.50|2026-01-15|EXTRA", 1)

    assert isinstance(parsed, LoadError)
    assert "expected 5 fields" in parsed.reason


def test_parse_lines_skips_blank_lines() -> None:
    records, errors = parse_lines(["\n", "TXN-000001|ACCT-123456|CREDIT|1.00|2026-01-15\n"])

    assert len(records) == 1
    assert errors == []


def test_parse_lines_accepts_crlf_fixture() -> None:
    with open("tests/fixtures/crlf_transactions.txt", encoding="utf-8", newline="") as file_obj:
        records, errors = parse_lines(file_obj.readlines())

    assert errors == []
    assert [record.txn_date for record in records] == ["2026-01-15", "2026-01-16"]
