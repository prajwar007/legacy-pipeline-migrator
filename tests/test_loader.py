from decimal import Decimal

import pytest

from pipeline.config import FieldMappingConfig
from pipeline.loader import load_transactions, main


def test_load_transactions_accumulates_totals_and_large_debits() -> None:
    result = load_transactions(
        [
            "TXN-000001|ACCT-123456|CREDIT|50.00|2026-01-15",
            "TXN-000002|ACCT-123456|DEBIT|12500.00|2026-01-16",
        ],
        large_debit_threshold=Decimal("10000.00"),
    )

    assert result.accepted_count == 2
    assert result.rejected_count == 0
    assert result.totals_by_type == {"CREDIT": Decimal("50.00"), "DEBIT": Decimal("12500.00")}
    assert [record.transaction_id for record in result.large_debits] == ["TXN-000002"]


def test_load_transactions_collects_parse_and_validation_errors() -> None:
    result = load_transactions(
        [
            "TXN-000001|ACCT-123456|DEBIT|12.00|2026-01-15|EXTRA",
            "TXN-000002|BAD|DEBIT|12.00|2026-01-15",
        ]
    )

    assert result.accepted_count == 0
    assert result.rejected_count == 2


def test_main_exits_nonzero_when_records_rejected(monkeypatch, tmp_path, capsys) -> None:
    # Matches the Perl baseline's `exit 1` when error_count > 0 — an
    # orchestrator relying on exit code must be able to detect a bad run.
    bad_file = tmp_path / "bad.txt"
    bad_file.write_text("TXN-000001|BAD|DEBIT|12.00|2026-01-15\n")

    monkeypatch.setattr("sys.argv", ["loader.py", str(bad_file)])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    assert "rejected=1" in capsys.readouterr().out


def test_main_exits_zero_when_all_records_accepted(monkeypatch, tmp_path) -> None:
    good_file = tmp_path / "good.txt"
    good_file.write_text("TXN-000001|ACCT-123456|CREDIT|12.00|2026-01-15\n")

    monkeypatch.setattr("sys.argv", ["loader.py", str(good_file)])

    main()  # should not raise


def test_field_mapping_config_actually_drives_validation() -> None:
    # Proves field_mapping.yaml (loaded into a FieldMappingConfig) is
    # genuinely wired in, not just loaded and ignored: an account_id
    # that's valid under the default rules is rejected under a custom,
    # stricter mapping passed in explicitly.
    custom_mapping = FieldMappingConfig(
        source_fields=["transaction_id", "account_id", "txn_type", "amount", "txn_date"],
        account_id_regex=r"^VIP-\d{4}$",
        transaction_id_regex=r"^TXN-\d{6}$",
        amount_regex=r"^\d+(\.\d{1,2})?$",
        valid_txn_types={"CREDIT", "DEBIT"},
    )

    result = load_transactions(
        ["TXN-000001|ACCT-123456|CREDIT|50.00|2026-01-15"],
        field_mapping=custom_mapping,
    )

    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert "invalid account_id" in result.errors[0].reason

