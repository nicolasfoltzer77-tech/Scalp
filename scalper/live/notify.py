# scalper/live/notify.py
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

import requests

log = logging.getLogger("scalper.live.notify")


class _NullNotifier:
    async def send(self, text: str) -> None:
        log.info("[NOTIFY] %s", text)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 5.0) -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    async def send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            # Appel sync dans thread pour rester simple
            def _post() -> None:
                requests.post(url, json=payload, timeout=self.timeout)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _post)
        except Exception:
            log.debug("Envoi Telegram échoué", exc_info=True)


async def _command_stream_stub() -> AsyncIterator[Dict[str, Any]]:
    """
    Générateur de commandes vide (placeholder).
    Peut être remplacé par une vraie source (websocket, telegram callbacks, etc.).
    """
    while False:
        yield {}


def build_notifier_and_commands(cfg: Dict[str, Any] | None = None) -> tuple[Any, AsyncIterator[Dict[str, Any]] | None]:
    """
    Retourne (notifier, command_stream)
    - Notifier Telegram si TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID présents, sinon Null.
    - Flux de commandes: stub None (l’orchestrateur gère le None).
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN") or (cfg or {}).get("secrets", {}).get("telegram", {}).get("token")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or (cfg or {}).get("secrets", {}).get("telegram", {}).get("chat_id")

    if token and chat_id:
        return TelegramNotifier(token, chat_id), None
    return _NullNotifier(), None