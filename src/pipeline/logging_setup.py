from __future__ import annotations

import logging.config
from pathlib import Path

import yaml


def configure_logging(path: str | Path = "config/logging.yaml") -> None:
    with Path(path).open(encoding="utf-8") as file_obj:
        config = yaml.safe_load(file_obj)
    if not isinstance(config, dict):
        raise ValueError("logging config must be a mapping")

    _ensure_handler_directories_exist(config)
    logging.config.dictConfig(config)


def _ensure_handler_directories_exist(config: dict) -> None:
    # logging.config.dictConfig will raise FileNotFoundError on a fresh
    # checkout if a handler's target directory (e.g. logs/) doesn't exist
    # yet — Python's logging module does not create it automatically.
    for handler in config.get("handlers", {}).values():
        filename = handler.get("filename")
        if filename:
            Path(filename).parent.mkdir(parents=True, exist_ok=True)

