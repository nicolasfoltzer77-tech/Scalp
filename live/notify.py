# live/notify.py
from __future__ import annotations
import asyncio
from typing import AsyncIterator, Optional

# on réutilise ton client existant
from live.telegram_async import TelegramAsync  # déjà dans ton repo

class Notifier:
    async def start(self): ...
    async def stop(self): ...
    async def send(self, text: str): ...

class NullNotifier(Notifier):
    async def start(self): pass
    async def stop(self): pass
    async def send(self, text: str): pass

class TelegramNotifier(Notifier):
    def __init__(self, token: Optional[str], chat_id: Optional[str]) -> None:
        self._tg = TelegramAsync(token=token, chat_id=chat_id) if token and chat_id else None
        self._run = False

    async def start(self):
        self._run = bool(self._tg and self._tg.enabled())

    async def stop(self):
        self._run = False

    async def send(self, text: str):
        if self._run and self._tg:
            await self._tg.send_message(text)

class CommandStream:
    """Lit les commandes Telegram et les expose comme un flux asynchrone décorrélé de l’orchestrateur."""
    def __init__(self, token: Optional[str], chat_id: Optional[str]) -> None:
        self._tg = TelegramAsync(token=token, chat_id=chat_id) if token and chat_id else None
        self._run = False

    async def __aiter__(self) -> AsyncIterator[str]:
        self._run = bool(self._tg and self._tg.enabled())
        while self._run:
            try:
                ups = await self._tg.poll_commands(timeout_s=20) if self._tg else []  # type: ignore
                for u in ups:
                    t = (u.get("text") or "").strip()
                    if t: yield t
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)

    async def stop(self):
        self._run = False