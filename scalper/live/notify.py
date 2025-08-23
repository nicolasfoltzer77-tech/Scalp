# scalper/live/notify.py
from __future__ import annotations

import asyncio
import aiohttp
import os
from typing import Any, Tuple


# ---------------------------------------------------------------------
# Notifier abstrait
# ---------------------------------------------------------------------
class BaseNotifier:
    async def send(self, text: str) -> None:
        raise NotImplementedError


class NullNotifier(BaseNotifier):
    async def send(self, text: str) -> None:
        # log console seulement
        print(f"[notify:null] {text}")


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def send(self, text: str) -> None:
        try:
            sess = await self._ensure_session()
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text}
            async with sess.post(url, json=payload, timeout=30) as r:
                if r.status != 200:
                    print(f"[notify:telegram] HTTP {r.status}")
        except Exception as e:  # noqa: BLE001
            print(f"[notify:telegram] error: {e}")


# ---------------------------------------------------------------------
# CommandStream (ex: commandes reçues via Telegram webhook)
# pour l’instant, mock simple = asyncio.Queue
# ---------------------------------------------------------------------
class CommandStream:
    def __init__(self):
        self.q: asyncio.Queue[str] = asyncio.Queue()

    async def get(self) -> str:
        return await self.q.get()

    async def put(self, cmd: str) -> None:
        await self.q.put(cmd)


# ---------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------
async def build_notifier_and_commands(config: dict[str, Any] | None = None) -> Tuple[BaseNotifier, CommandStream]:
    """
    Construit un Notifier + CommandStream.
    Si config contient TELEGRAM_TOKEN et TELEGRAM_CHAT_ID → TelegramNotifier,
    sinon NullNotifier.
    """
    config = config or {}

    token = config.get("TELEGRAM_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    chat_id = config.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")

    if token and chat_id:
        notifier = TelegramNotifier(token, chat_id)
        cmd_stream = CommandStream()
        print("[notify] Using Telegram notifier/commands")
    else:
        notifier = NullNotifier()
        cmd_stream = CommandStream()
        print("[notify] Using Null notifier/commands")

    return notifier, cmd_stream