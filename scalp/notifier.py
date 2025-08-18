"""Simple notifier for bot events."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

try:  # pragma: no cover - guarded import for optional dependency
    import requests as _requests

    # ``requests`` may be provided as a stub during tests. Ensure it exposes a
    # ``post`` attribute so callers can monkeypatch it reliably.
    if not hasattr(_requests, "post"):
        raise ImportError
    requests = _requests
except Exception:  # pragma: no cover - fallback when ``requests`` is missing

    class _Requests:
        """Minimal stand‑in for :mod:`requests` when the real library is absent."""

        def post(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - safety
            raise RuntimeError("requests.post unavailable")

    requests = _Requests()  # type: ignore[assignment]


def _pair_name(symbol: str) -> str:
    """Return a human friendly pair name like ``BTC/USDT``."""
    if "_" in symbol:
        base, quote = symbol.split("_", 1)
    elif symbol.endswith("USDT"):
        base, quote = symbol[:-4], "USDT"
    else:
        base, quote = symbol, ""
    return f"{base}/{quote}" if quote else base


def _format_text(event: str, payload: Dict[str, Any] | None = None) -> str:
    """Return a human readable text describing the event payload."""
    if event in {"position_opened", "position_closed"}:
        action = "Ouvre" if event == "position_opened" else "Ferme"
        side = payload.get("side") if payload else None
        symbol = payload.get("symbol") if payload else None
        if symbol:
            symbol = _pair_name(symbol)
        head = " ".join(p for p in [action, side, symbol] if p)

        lines = [head]
        if payload:
            vol = payload.get("vol")
            lev = payload.get("leverage")
            if vol is not None and lev is not None:
                lines.append(f"Position: {vol} x{lev}")

            if event == "position_opened":
                tp_usd = payload.get("tp_usd")
                sl_usd = payload.get("sl_usd")
                if tp_usd is not None and sl_usd is not None:
                    lines.append(f"TP: +{tp_usd} USDT / SL: -{sl_usd} USDT")
                else:
                    tp = payload.get("tp_pct")
                    sl = payload.get("sl_pct")
                    if tp is not None and sl is not None:
                        lines.append(f"TP: +{tp}% / SL: -{sl}%")
                hold = payload.get("hold") or payload.get("expected_duration")
                if hold is not None:
                    lines.append(f"Durée prévue: {hold}")
            else:  # position_closed
                pnl_usd = payload.get("pnl_usd")
                pnl_pct = payload.get("pnl_pct")
                if pnl_usd is not None and pnl_pct is not None:
                    lines.append(f"PnL: {pnl_usd} USDT ({pnl_pct}%)")
                elif pnl_pct is not None:
                    lines.append(f"PnL: {pnl_pct}%")
                dur = payload.get("duration")
                if dur is not None:
                    lines.append(f"Durée: {dur}")
        return "\n".join(lines)

    text = event
    if payload:
        items = "\n".join(f"{k}={v}" for k, v in payload.items())
        text = f"{text}\n{items}"
    return text


def notify(event: str, payload: Dict[str, Any] | None = None) -> None:
    """Send an event payload to configured endpoints.

    Notifications can be delivered via a generic HTTP endpoint defined by
    ``NOTIFY_URL`` and/or directly to Telegram when ``TELEGRAM_BOT_TOKEN`` and
    ``TELEGRAM_CHAT_ID`` are provided. Missing configuration for one notifier
    doesn't affect the others. Network errors are logged but otherwise ignored
    so they don't interrupt the bot's execution.
    """

    data = {"event": event}
    if payload:
        data.update(payload)

    # Generic HTTP webhook
    url = os.getenv("NOTIFY_URL")
    if url:
        try:
            requests.post(url, json=data, timeout=5)
        except Exception as exc:  # pragma: no cover - best effort only
            logging.error("Notification error for %s: %s", event, exc)

    # Telegram bot notification
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        tg_payload = {"chat_id": chat_id, "text": _format_text(event, payload)}
        try:
            requests.post(tg_url, json=tg_payload, timeout=5)
        except Exception as exc:  # pragma: no cover - best effort only
            logging.error("Telegram notification error for %s: %s", event, exc)
