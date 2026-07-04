from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("pipeline.alerting")

WEBHOOK_ENV_VAR = "ALERT_WEBHOOK_URL"
REQUEST_TIMEOUT_SECONDS = 5


def send_alert(message: str, webhook_url: str | None = None) -> bool:
    """Post an alert to a Slack-compatible incoming webhook.

    Returns True if the alert was sent, False if it was skipped (no
    webhook configured) or failed. Deliberately never raises — a broken
    alert channel should never itself take down the pipeline or mask the
    original failure that triggered the alert.
    """
    url = webhook_url or os.environ.get(WEBHOOK_ENV_VAR)
    if not url:
        # No webhook configured (e.g. local dev, CI, or an environment
        # that hasn't set this up yet) — this is expected, not an error,
        # so it stays at debug level rather than warning/error noise.
        logger.debug("No %s configured; skipping alert webhook.", WEBHOOK_ENV_VAR)
        return False

    payload = json.dumps({"text": message}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            success = 200 <= response.status < 300
            if not success:
                logger.error("Alert webhook returned status %s", response.status)
            return success
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.error("Failed to send alert webhook: %s", exc)
        return False
