from __future__ import annotations

from collections.abc import Iterable

from pipeline.models import LoadError, RawTransactionRecord

EXPECTED_FIELD_COUNT = 5


def parse_line(line: str, line_number: int) -> RawTransactionRecord | LoadError | None:
    raw_line = line.rstrip("\n")
    if not raw_line.strip():
        return None

    parts = raw_line.split("|")
    if len(parts) != EXPECTED_FIELD_COUNT:
        return LoadError(
            line_number=line_number,
            raw_line=raw_line,
            reason=f"expected {EXPECTED_FIELD_COUNT} fields, found {len(parts)}",
        )

    return RawTransactionRecord(
        transaction_id=parts[0].strip(),
        account_id=parts[1].strip(),
        txn_type=parts[2].strip().upper(),
        amount=parts[3].strip(),
        txn_date=parts[4].strip(),
        line_number=line_number,
        raw_line=raw_line,
    )


def parse_lines(lines: Iterable[str]) -> tuple[list[RawTransactionRecord], list[LoadError]]:
    records: list[RawTransactionRecord] = []
    errors: list[LoadError] = []

    for line_number, line in enumerate(lines, start=1):
        parsed = parse_line(line, line_number)
        if parsed is None:
            continue
        if isinstance(parsed, LoadError):
            errors.append(parsed)
        else:
            records.append(parsed)

    return records, errors

