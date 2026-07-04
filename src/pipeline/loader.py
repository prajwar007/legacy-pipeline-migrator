from __future__ import annotations

import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from pipeline.config import FieldMappingConfig, load_field_mapping, load_thresholds
from pipeline.models import LoadError, LoadResult, TransactionRecord
from pipeline.parse import parse_lines
from pipeline.validate import DEFAULT_FIELD_MAPPING, validate_record

DEFAULT_LARGE_DEBIT_THRESHOLD = Decimal("10000.00")


def load_transactions(
    lines: list[str],
    *,
    large_debit_threshold: Decimal = DEFAULT_LARGE_DEBIT_THRESHOLD,
    field_mapping: FieldMappingConfig = DEFAULT_FIELD_MAPPING,
) -> LoadResult:
    raw_records, parse_errors = parse_lines(lines)
    result = LoadResult(errors=list(parse_errors))
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)

    for raw in raw_records:
        validated = validate_record(raw, field_mapping)
        if isinstance(validated, LoadError):
            result.errors.append(validated)
            continue

        result.records.append(validated)
        totals[validated.txn_type] += validated.amount
        if is_large_debit(validated, large_debit_threshold):
            result.large_debits.append(validated)

    result.totals_by_type = dict(totals)
    return result


def load_transaction_file(
    path: str | Path,
    *,
    large_debit_threshold: Decimal = DEFAULT_LARGE_DEBIT_THRESHOLD,
    field_mapping: FieldMappingConfig = DEFAULT_FIELD_MAPPING,
) -> LoadResult:
    with Path(path).open(encoding="utf-8") as file_obj:
        return load_transactions(
            file_obj.readlines(),
            large_debit_threshold=large_debit_threshold,
            field_mapping=field_mapping,
        )


def is_large_debit(record: TransactionRecord, threshold: Decimal) -> bool:
    return record.txn_type == "DEBIT" and record.amount > threshold


def main() -> None:
    parser = argparse.ArgumentParser(description="Load and summarize transaction file")
    parser.add_argument("path")
    parser.add_argument("--thresholds", default="config/thresholds.yaml")
    parser.add_argument("--field-mapping", default="config/field_mapping.yaml")
    args = parser.parse_args()

    thresholds = load_thresholds(args.thresholds)
    field_mapping = load_field_mapping(args.field_mapping)
    result = load_transaction_file(
        args.path,
        large_debit_threshold=thresholds.large_debit_threshold,
        field_mapping=field_mapping,
    )

    print(f"accepted={result.accepted_count} rejected={result.rejected_count}")
    for txn_type, total in sorted(result.totals_by_type.items()):
        print(f"{txn_type}={total:.2f}")
    print(f"large_debits={len(result.large_debits)}")

    if result.rejected_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
