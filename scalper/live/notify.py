# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional


@dataclass
class BaseNotifier:
    async def send(self, text: str) -> None:  # pragma: no cover
        print(text)


class NullNotifier(BaseNotifier):
    pass


class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str, chat_id: str, session: Optional[asyncio.AbstractEventLoop]=None):
        import aiohttp  # lazy
        self._token = token
        self._chat = chat_id
        self._session: aiohttp.ClientSession | None = None

    async def _ensure(self):
        import aiohttp
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def send(self, text: str) -> None:
        import aiohttp
        await self._ensure()
        # pas de markdown pour éviter les erreurs 400 de parsing
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": self._chat, "text": text, "disable_web_page_preview": True}
        try:
            async with self._session.post(url, json=payload, timeout=20) as r:
                await r.text()  # on ignore la réponse pour rester simple
        except Exception:
            # on fait un fallback silencieux pour ne pas casser le bot
            print("[notify:telegram] send fail (ignored)")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


class _NullCommands:
    """Itérateur async vide utilisé quand Telegram n'est pas configuré."""
    def __aiter__(self) -> AsyncIterator[str]:
        return self
    async def __anext__(self) -> str:
        await asyncio.sleep(3600)  # jamais
        raise StopAsyncIteration


async def build_notifier_and_commands(config: dict) -> tuple[BaseNotifier, AsyncIterator[str]]:
    """
    Retourne (notifier, command_stream).

    - Si TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont présents: TelegramNotifier,
      et un flux (vide) – l’orchestreur n’en a besoin que si on implémente des
      commandes interactives plus tard.
    - Sinon: NullNotifier + flux vide.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        print("[notify] TELEGRAM configured.")
        return TelegramNotifier(token, chat), _NullCommands()
    print("[notify] TELEGRAM not configured -> Null notifier will be used.")
    return NullNotifier(), _NullCommands()