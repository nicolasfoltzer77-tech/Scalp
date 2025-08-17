"""Simple HTTP notifier for bot events."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests


def notify(event: str, payload: Dict[str, Any] | None = None) -> None:
    """Send an event payload to the URL defined by ``NOTIFY_URL``.

    If the ``NOTIFY_URL`` environment variable is absent, the function does
    nothing. Network errors are logged but otherwise ignored so they don't
    interrupt the bot's execution.
    """
    url = os.getenv("NOTIFY_URL")
    if not url:
        logging.debug("NOTIFY_URL not set; skipping notification for %s", event)
        return

    data = {"event": event}
    if payload:
        data.update(payload)

    try:
        requests.post(url, json=data, timeout=5)
    except Exception as exc:  # pragma: no cover - best effort only
        logging.error("Notification error for %s: %s", event, exc)
