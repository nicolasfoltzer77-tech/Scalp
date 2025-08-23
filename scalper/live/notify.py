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
        # Pas de parse_mode pour éviter “can't parse entities…”
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": msg, "disable_web_page_preview": True}
        async with self.session.post(url, json=payload) as r:
            if r.status >= 400:
                txt = await r.text()
                print(f"[notify:telegram] HTTP {r.status}: {txt}")

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class NullCommandStream:
    """
    Itérateur asynchrone infini qui n'émet… rien d’utile.
    Permet à `async for` de tourner sans générer d’exceptions/CPU.
    """
    def __init__(self, period: float = 3600.0) -> None:
        self.period = period

    def __aiter__(self) -> "NullCommandStream":
        return self

    async def __anext__(self) -> str:
        await asyncio.sleep(self.period)
        return ""  # _handle_command() ignore les chaînes vides


async def build_notifier_and_commands(config) -> Tuple[BaseNotifier, AsyncIterator[str]]:
    """
    Retourne (notifier, command_stream). Si TELEGRAM_* absent => Null.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT")

    if token and chat:
        print("[notify] Using Telegram notifier/commands")
        # Pour l’instant on ne “poll” pas les commandes, on garde un stream nul.
        return TelegramNotifier(token, chat), NullCommandStream()

    print("[notify] Using Null notifier/commands")
    return NullNotifier(), NullCommandStream()