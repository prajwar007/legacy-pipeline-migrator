from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from pipeline.alerting import send_alert


def test_send_alert_skips_when_no_webhook_configured(monkeypatch) -> None:
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)

    with patch("pipeline.alerting.urllib.request.urlopen") as mock_urlopen:
        result = send_alert("pipeline failed")

    assert result is False
    mock_urlopen.assert_not_called()


def test_send_alert_posts_json_to_configured_webhook(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example.test/webhook")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response

    with patch(
        "pipeline.alerting.urllib.request.urlopen", return_value=mock_response
    ) as mock_urlopen:
        result = send_alert("pipeline failed: task=load_to_oracle run_id=abc123")

    assert result is True
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "https://hooks.example.test/webhook"
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data.decode("utf-8"))
    assert body == {"text": "pipeline failed: task=load_to_oracle run_id=abc123"}


def test_send_alert_explicit_url_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://env-configured.example.test")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response

    with patch(
        "pipeline.alerting.urllib.request.urlopen", return_value=mock_response
    ) as mock_urlopen:
        send_alert("hello", webhook_url="https://explicit.example.test")

    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "https://explicit.example.test"


def test_send_alert_returns_false_on_non_2xx_status(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example.test/webhook")

    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.__enter__.return_value = mock_response

    with patch("pipeline.alerting.urllib.request.urlopen", return_value=mock_response):
        result = send_alert("pipeline failed")

    assert result is False


def test_send_alert_never_raises_on_network_failure(monkeypatch) -> None:
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example.test/webhook")

    with patch(
        "pipeline.alerting.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        # Must not raise — a broken alert channel shouldn't mask or
        # compound the original pipeline failure that triggered it.
        result = send_alert("pipeline failed")

    assert result is False
