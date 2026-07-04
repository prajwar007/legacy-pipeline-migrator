from __future__ import annotations

from unittest.mock import MagicMock, patch

from dags.transaction_pipeline_dag import _log_failure


def test_log_failure_logs_and_sends_alert() -> None:
    context = {
        "task_instance": MagicMock(task_id="load_to_oracle"),
        "dag_run": MagicMock(run_id="manual__2026-01-15"),
        "exception": ValueError("Oracle connection refused"),
    }

    with patch("pipeline.alerting.send_alert") as mock_send_alert:
        _log_failure(context)

    mock_send_alert.assert_called_once()
    (message,), _kwargs = mock_send_alert.call_args
    assert "load_to_oracle" in message
    assert "manual__2026-01-15" in message
    assert "Oracle connection refused" in message


def test_log_failure_handles_missing_context_gracefully() -> None:
    # Airflow always populates these, but the callback shouldn't crash
    # if it's ever invoked with a partial context (e.g. in a test harness).
    with patch("pipeline.alerting.send_alert") as mock_send_alert:
        _log_failure({})

    mock_send_alert.assert_called_once()
    (message,), _kwargs = mock_send_alert.call_args
    assert "unknown" in message
