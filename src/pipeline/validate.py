from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from pipeline.config import FieldMappingConfig
from pipeline.models import LoadError, RawTransactionRecord, TransactionRecord

# Default validation rules, used when no FieldMappingConfig is supplied.
# Kept in sync with config/field_mapping.yaml — prefer loading that file
# via pipeline.config.load_field_mapping() in real entrypoints so rules
# stay config-driven rather than hardcoded.
DEFAULT_FIELD_MAPPING = FieldMappingConfig(
    source_fields=["transaction_id", "account_id", "txn_type", "amount", "txn_date"],
    account_id_regex=r"^ACCT-\d{6}$",
    transaction_id_regex=r"^TXN-\d{6}$",
    amount_regex=r"^\d+(\.\d{1,2})?$",
    valid_txn_types={"CREDIT", "DEBIT"},
)


@lru_cache(maxsize=32)
def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def validate_record(
    raw: RawTransactionRecord,
    field_mapping: FieldMappingConfig = DEFAULT_FIELD_MAPPING,
) -> TransactionRecord | LoadError:
    errors: list[str] = []

    transaction_id_re = _compiled(field_mapping.transaction_id_regex)
    account_id_re = _compiled(field_mapping.account_id_regex)
    amount_re = _compiled(field_mapping.amount_regex)

    if not transaction_id_re.match(raw.transaction_id):
        errors.append("invalid transaction_id")
    if not account_id_re.match(raw.account_id):
        errors.append("invalid account_id")
    if raw.txn_type not in field_mapping.valid_txn_types:
        errors.append("invalid txn_type")

    amount = Decimal("0")
    if amount_re.match(raw.amount):
        try:
            amount = Decimal(raw.amount)
        except InvalidOperation:
            errors.append("invalid amount")
    else:
        errors.append("invalid amount")

    try:
        txn_date = date.fromisoformat(raw.txn_date)
    except ValueError:
        txn_date = date.min
        errors.append("invalid date")

    if errors:
        return LoadError(raw.line_number, raw.raw_line, "; ".join(errors))

    return TransactionRecord(
        transaction_id=raw.transaction_id,
        account_id=raw.account_id,
        txn_type=raw.txn_type,
        amount=amount,
        txn_date=txn_date,
        line_number=raw.line_number,
    )
