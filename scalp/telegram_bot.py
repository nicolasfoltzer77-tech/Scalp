from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    import requests as _requests
    requests = _requests
except Exception:  # pragma: no cover
    class _Requests:
        def get(self, *a: Any, **k: Any) -> Any:  # pragma: no cover - fallback
            raise RuntimeError("requests.get unavailable")

        def post(self, *a: Any, **k: Any) -> Any:  # pragma: no cover - fallback
            raise RuntimeError("requests.post unavailable")

    requests = _Requests()  # type: ignore[assignment]


class TelegramBot:
    """Minimal Telegram bot using the HTTP API.

    It polls updates and answers a few text commands allowing the user to
    inspect the trading session.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        client: Any,
        config: Dict[str, Any],
        *,
        requests_module: Any = requests,
    ) -> None:
        self.token = token
        self.chat_id = str(chat_id)
        self.client = client
        self.config = config
        self.requests = requests_module
        self.last_update_id: Optional[int] = None

    # ------------------------------------------------------------------
    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    def send(self, text: str) -> None:
        payload = {"chat_id": self.chat_id, "text": text}
        try:  # pragma: no cover - network
            self.requests.post(self._api_url("sendMessage"), json=payload, timeout=5)
        except Exception as exc:  # pragma: no cover - best effort
            logging.error("Telegram send error: %s", exc)

    # ------------------------------------------------------------------
    def fetch_updates(self) -> list[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if self.last_update_id is not None:
            params["offset"] = self.last_update_id + 1
        try:  # pragma: no cover - network
            r = self.requests.get(self._api_url("getUpdates"), params=params, timeout=5)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # pragma: no cover - best effort
            logging.error("Telegram getUpdates error: %s", exc)
            return []
        updates = data.get("result", [])
        if updates:
            self.last_update_id = updates[-1].get("update_id")
        return updates

    # ------------------------------------------------------------------
    def handle_updates(self, session_pnl: float) -> None:
        for update in self.fetch_updates():
            msg = update.get("message") or {}
            chat = msg.get("chat") or {}
            if str(chat.get("id")) != self.chat_id:
                continue
            text = msg.get("text", "")
            reply = self.handle_command(text, session_pnl)
            if reply:
                self.send(reply)

    # ------------------------------------------------------------------
    def handle_command(self, text: str, session_pnl: float) -> Optional[str]:
        if not text:
            return None
        parts = text.strip().split()
        cmd = parts[0].lower()
        arg = parts[1:] if len(parts) > 1 else []

        if cmd == "/help":
            return (
                "Commandes:\n"
                "/balance - solde compte\n"
                "/positions - positions ouvertes\n"
                "/pnl - PnL session\n"
                "/risk [1-3] - niveau de risque"
            )
        if cmd == "/balance":
            assets = self.client.get_assets()
            equity = 0.0
            for row in assets.get("data", []):
                if row.get("currency") == "USDT":
                    try:
                        equity = float(row.get("equity", 0.0))
                    except Exception:
                        equity = 0.0
                    break
            return f"Solde: {equity} USDT"
        if cmd == "/positions":
            pos = self.client.get_positions()
            lines = []
            for p in pos.get("data", []):
                symbol = p.get("symbol")
                side = p.get("side")
                vol = p.get("vol")
                lines.append(f"{symbol} {side} {vol}")
            if not lines:
                return "Aucune position ouverte"
            return "Positions:\n" + "\n".join(lines)
        if cmd in {"/pnl", "/session"}:
            return f"PnL session: {session_pnl} USDT"
        if cmd == "/risk":
            if arg:
                try:
                    lvl = int(arg[0])
                    if lvl in (1, 2, 3):
                        self.config["RISK_LEVEL"] = lvl
                        return f"Niveau de risque réglé sur {lvl}"
                except ValueError:
                    pass
            return f"Niveau de risque actuel: {self.config.get('RISK_LEVEL', 2)}"
        return "Commande inconnue. Tapez /help"


def init_telegram_bot(client: Any, config: Dict[str, Any]) -> Optional[TelegramBot]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return TelegramBot(token, chat_id, client, config)
    return None
