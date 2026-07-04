from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class RawTransactionRecord:
    transaction_id: str
    account_id: str
    txn_type: str
    amount: str
    txn_date: str
    line_number: int
    raw_line: str


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: str
    account_id: str
    txn_type: str
    amount: Decimal
    txn_date: date
    line_number: int


@dataclass(frozen=True)
class LoadError:
    line_number: int
    raw_line: str
    reason: str


@dataclass
class LoadResult:
    records: list[TransactionRecord] = field(default_factory=list)
    errors: list[LoadError] = field(default_factory=list)
    totals_by_type: dict[str, Decimal] = field(default_factory=dict)
    large_debits: list[TransactionRecord] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return len(self.records)

    @property
    def rejected_count(self) -> int:
        return len(self.errors)


@dataclass(frozen=True)
class ReconciliationResult:
    matched: bool
    missing_in_target: frozenset[str] = field(default_factory=frozenset)
    unexpected_in_target: frozenset[str] = field(default_factory=frozenset)

