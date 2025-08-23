# scalper/live/notify.py
from __future__ import annotations
import os
import asyncio
from typing import AsyncIterator, Tuple, Any, Optional

import aiohttp


class BaseNotifier:
    async def send(self, msg: str) -> None:
        raise NotImplementedError


class NullNotifier(BaseNotifier):
    async def send(self, _msg: str) -> None:
        return


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._session

    async def send(self, msg: str) -> None:
        # send without parse_mode to avoid "can't parse entities"
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": msg, "disable_web_page_preview": True}
        async with self.session.post(url, json=payload) as r:
            if r.status >= 400:
                txt = await r.text()
                print(f"[notify:telegram] HTTP {r.status}: {txt}")

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


async def _null_commands() -> AsyncIterator[str]:
    # simple async generator that never yields commands
    while True:
        await asyncio.sleep(3600)


async def build_notifier_and_commands(config) -> Tuple[BaseNotifier, AsyncIterator[str]]:
    """Return (notifier, command_stream). Falls back to Null when tokens are missing."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT")

    if token and chat:
        print("[notify] Using Telegram notifier/commands")
        # Commands: for now we keep only outgoing (no polling) — separate runner handles commands if needed.
        return TelegramNotifier(token, chat), _null_commands()

    print("[notify] Using Null notifier/commands")
    return NullNotifier(), _null_commands()