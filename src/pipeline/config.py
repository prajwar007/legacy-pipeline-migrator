from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ThresholdConfig:
    large_debit_threshold: Decimal


@dataclass(frozen=True)
class FieldMappingConfig:
    source_fields: list[str]
    account_id_regex: str
    transaction_id_regex: str
    amount_regex: str
    valid_txn_types: set[str]


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file_obj:
        data = yaml.safe_load(file_obj)
    if not isinstance(data, dict):
        raise ValueError(f"YAML config must be a mapping: {path}")
    return data


def load_thresholds(path: str | Path) -> ThresholdConfig:
    data = load_yaml(path)
    value = data.get("large_debit_threshold")
    if value is None:
        raise ValueError("large_debit_threshold is required")
    return ThresholdConfig(large_debit_threshold=Decimal(str(value)))


def load_field_mapping(path: str | Path) -> FieldMappingConfig:
    data = load_yaml(path)
    validation = data.get("validation")
    if not isinstance(validation, dict):
        raise ValueError("validation mapping is required")

    source_fields = data.get("source_fields")
    if not isinstance(source_fields, list) or not all(
        isinstance(item, str) for item in source_fields
    ):
        raise ValueError("source_fields must be a list of strings")

    valid_txn_types = validation.get("valid_txn_types")
    if not isinstance(valid_txn_types, list) or not all(
        isinstance(item, str) for item in valid_txn_types
    ):
        raise ValueError("validation.valid_txn_types must be a list of strings")

    return FieldMappingConfig(
        source_fields=source_fields,
        account_id_regex=_required_str(validation, "account_id_regex"),
        transaction_id_regex=_required_str(validation, "transaction_id_regex"),
        amount_regex=_required_str(validation, "amount_regex"),
        valid_txn_types=set(valid_txn_types),
    )


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value
