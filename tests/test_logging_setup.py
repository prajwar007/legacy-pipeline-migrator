from __future__ import annotations

import logging

from pipeline.logging_setup import configure_logging


def test_configure_logging_creates_missing_log_directory(tmp_path) -> None:
    log_dir = tmp_path / "logs"
    log_file = log_dir / "pipeline.log"
    config_path = tmp_path / "logging.yaml"
    config_path.write_text(
        f"""
version: 1
disable_existing_loggers: false
formatters:
  standard:
    format: "%(asctime)s %(levelname)s %(name)s %(message)s"
handlers:
  file:
    class: logging.FileHandler
    level: INFO
    formatter: standard
    filename: {log_file}
loggers:
  pipeline_test_logger:
    level: INFO
    handlers: [file]
    propagate: false
"""
    )

    assert not log_dir.exists()

    configure_logging(config_path)

    assert log_dir.exists()

    logger = logging.getLogger("pipeline_test_logger")
    logger.info("hello")
    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    assert "hello" in log_file.read_text()
