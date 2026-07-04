from pipeline.models import LoadError, RawTransactionRecord, TransactionRecord
from pipeline.validate import validate_record


def _raw(**overrides: str) -> RawTransactionRecord:
    values = {
        "transaction_id": "TXN-000001",
        "account_id": "ACCT-123456",
        "txn_type": "DEBIT",
        "amount": "99.95",
        "txn_date": "2026-01-15",
    }
    values.update(overrides)
    return RawTransactionRecord(line_number=1, raw_line="raw", **values)


def test_validate_accepts_valid_record() -> None:
    result = validate_record(_raw())

    assert isinstance(result, TransactionRecord)
    assert result.account_id == "ACCT-123456"


def test_validate_rejects_bad_account_id() -> None:
    result = validate_record(_raw(account_id="123456"))

    assert isinstance(result, LoadError)
    assert "invalid account_id" in result.reason


def test_validate_rejects_bad_txn_type_amount_and_date() -> None:
    result = validate_record(_raw(txn_type="REFUND", amount="10.999", txn_date="2026-02-30"))

    assert isinstance(result, LoadError)
    assert "invalid txn_type" in result.reason
    assert "invalid amount" in result.reason
    assert "invalid date" in result.reason


def test_validate_rejects_impossible_calendar_date() -> None:
    result = validate_record(_raw(txn_date="2026-13-01"))

    assert isinstance(result, LoadError)
    assert "invalid date" in result.reason


def test_validate_rejects_negative_amount() -> None:
    # The Perl baseline documents amounts as intentionally positive-only,
    # since DEBIT/CREDIT already carries the direction. A negative amount
    # must be rejected, not silently accepted.
    result = validate_record(_raw(amount="-500.00"))

    assert isinstance(result, LoadError)
    assert "invalid amount" in result.reason
