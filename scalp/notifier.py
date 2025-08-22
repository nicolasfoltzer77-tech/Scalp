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
    if event == "position_opened":
        amt = payload.get("amount_usdt")
        if amt is not None:
            lines.append(f"Montant: {amt} USDT")
    else:
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
        rc = payload.get("risk_color")
        if rc:
            lvl = payload.get("sig_level")
            score = payload.get("score")
            lines.append(f"Risque: {rc} L{lvl} score {score}")
        rp = payload.get("risk_pct_eff")
        lev_eff = payload.get("leverage_eff")
        if rp is not None and lev_eff is not None:
            lines.append(f"Risk%: {rp:.4f} Levier eff.: x{lev_eff}")
        req = payload.get("required_margin")
        avail = payload.get("available")
        if req is not None and avail is not None:
            lines.append(f"Marge: {req:.2f}/{avail}")
        vb = payload.get("vol_before")
        vf = payload.get("vol")
        if vb is not None and vf is not None and vb != vf:
            lines.append(f"Vol: {vb}->{vf}")
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
