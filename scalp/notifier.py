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
    """Return a human friendly pair name without the base ``USDT``."""
    if "_" in symbol:
        base, quote = symbol.split("_", 1)
    elif symbol.endswith("USDT"):
        base, quote = symbol[:-4], "USDT"
    else:
        base, quote = symbol, ""
    if not quote or quote == "USDT":
        return base
    return f"{base}/{quote}"


def _format_position_event(event: str, payload: Dict[str, Any]) -> str:
    """Format a position open/close payload."""
    action = "Ouvre" if event == "position_opened" else "Ferme"
    side = payload.get("side")
    if side:
        side = f"{side} {'📈' if side == 'long' else '📉'}"
    symbol = payload.get("symbol")
    if symbol:
        symbol = _pair_name(symbol)
    pnl_pct = payload.get("pnl_pct")
    icons = ""
    if event == "position_closed" and pnl_pct is not None:
        icons = "✅🎯" if pnl_pct > 0 else "❌🛑"
    head = " ".join(p for p in [action, side, symbol, icons] if p)

    lines = [head]
    vol = payload.get("vol")
    if vol is not None:
        lines.append(f"Position: {vol}")
    lev = payload.get("leverage")
    if lev is not None:
        lines.append(f"Levier: x{lev}")
    if event == "position_opened":
        tp_usd = payload.get("tp_usd")
        sl_usd = payload.get("sl_usd")
        if tp_usd is not None and sl_usd is not None:
            lines.append(f"TP: +{tp_usd} USDT")
            lines.append(f"SL: -{sl_usd} USDT")
        else:
            tp = payload.get("tp_pct")
            sl = payload.get("sl_pct")
            if tp is not None and sl is not None:
                lines.append(f"TP: +{tp:.2f}%")
                lines.append(f"SL: -{sl:.2f}%")
        hold = payload.get("hold") or payload.get("expected_duration")
        if hold is not None:
            lines.append(f"Durée prévue: {hold}")
    else:  # position_closed
        pnl_usd = payload.get("pnl_usd")
        if pnl_usd is not None and pnl_pct is not None:
            lines.append(f"PnL: {pnl_usd} USDT ({pnl_pct:.2f}%)")
        elif pnl_pct is not None:
            lines.append(f"PnL: {pnl_pct:.2f}%")
        dur = payload.get("duration")
        if dur is not None:
            lines.append(f"Durée: {dur}")
    return "\n".join(lines)


def _format_pair_list(payload: Dict[str, Any]) -> str:
    """Format the pair list payload."""
    green = payload.get("green")
    orange = payload.get("orange")
    red = payload.get("red")
    if green or orange or red:
        lines = ["Listing :"]
        if green:
            lines.append(f"🟢 {green}")
        if orange:
            lines.append(f"🟠 {orange}")
        if red:
            lines.append(f"🔴 {red}")
        return "\n".join(lines)
    pairs = payload.get("pairs", "")
    return f"Listing : {pairs}"


def _format_generic(event: str, payload: Dict[str, Any]) -> str:
    text = event
    if payload:
        items = "\n".join(f"{k}={v}" for k, v in payload.items())
        text = f"{text}\n{items}"
    return text


def _format_text(event: str, payload: Dict[str, Any] | None = None) -> str:
    """Return a human readable text describing the event payload."""
    payload = payload or {}
    if event in {"position_opened", "position_closed"}:
        return _format_position_event(event, payload)
    if event == "pair_list":
        return _format_pair_list(payload)
    if event == "bot_started":
        return "🤖 Bot démarré"
    return _format_generic(event, payload)


def notify(event: str, payload: Dict[str, Any] | None = None) -> None:
    """Send an event payload to a configured HTTP endpoint.

    Notifications are delivered via a generic webhook defined by
    ``NOTIFY_URL``. Network errors are logged but otherwise ignored so they do
    not interrupt the bot's execution.
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
