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

    side = payload.get("side")
    symbol = payload.get("symbol")
    if symbol:
        symbol = _pair_name(symbol)

    if event == "position_opened":
        rc = payload.get("risk_color", "")
        head = f"{rc} Ouvre {side} {symbol}".strip()
        lines = [head]
        lines.append(
            f"Notional: {payload.get('notional_usdt')} USDT   Levier: x{payload.get('leverage')}"
        )
        lines.append(
            "Marge estimée: {} USDT (dispo: {} USDT)".format(
                payload.get("required_margin_usdt"), payload.get("available_usdt")
            )
        )
        lines.append(
            "Risque: lvl {}/{} (risk_pct={:.4f}%)".format(
                payload.get("signal_level"),
                payload.get("risk_level_user"),
                float(payload.get("risk_pct_eff", 0.0)) * 100,
            )
        )
        lines.append(
            "Prix: {}   Vol: {} (cs={})".format(
                payload.get("price"),
                payload.get("vol"),
                payload.get("contract_size"),
            )
        )
        return "\n".join(lines)

    # position_closed
    rc = payload.get("risk_color", "")
    head = f"Ferme {side} {symbol} {rc}".strip()
    lines = [head]
    pnl_usdt = payload.get("pnl_usdt")
    fees = payload.get("fees_usdt")
    if pnl_usdt is not None and fees is not None:
        lines.append(f"PnL net: {pnl_usdt:+.2f} USDT (frais: {fees:.2f})")
    pct = payload.get("pnl_pct_on_margin")
    if pct is not None:
        lines.append(f"% sur marge: {pct:.2f}%")
    lines.append(
        "Entrée: {}  Sortie: {}".format(
            payload.get("entry_price"), payload.get("exit_price")
        )
    )
    lines.append(
        "Vol: {}  Notional: in {} → out {} USDT".format(
            payload.get("vol"),
            payload.get("notional_entry_usdt"),
            payload.get("notional_exit_usdt"),
        )
    )
    return "\n".join(lines)


def _format_pair_list(payload: Dict[str, Any]) -> str:
    """Format the pair list payload.

    The detailed pair listing is intentionally hidden from terminal output to
    reduce noise. Only an acknowledgement message is returned.
    """

    return "Listing ok"


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
    """Send an event payload to configured endpoints.

    Notifications are delivered via a generic webhook defined by ``NOTIFY_URL``
    and/or directly to Telegram when ``TELEGRAM_BOT_TOKEN`` and
    ``TELEGRAM_CHAT_ID`` are provided. Network errors are logged but otherwise
    ignored so they do not interrupt the bot's execution.
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

    # Telegram notification
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    # ``pair_list`` notifications are intentionally not forwarded to Telegram
    if token and chat_id and event != "pair_list":
        text = _format_text(event, payload or {})
        t_url = f"https://api.telegram.org/bot{token}/sendMessage"
        t_payload = {"chat_id": chat_id, "text": text}
        try:  # pragma: no cover - network
            requests.post(t_url, json=t_payload, timeout=5)
        except Exception as exc:  # pragma: no cover - best effort only
            logging.error("Telegram notification error for %s: %s", event, exc)
