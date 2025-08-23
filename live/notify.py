# scalp/live/notify.py
from __future__ import annotations
import asyncio
from typing import AsyncIterator, Optional

# on réutilise ton client existant (déjà présent dans le repo)
from live.telegram_async import TelegramAsync  # type: ignore


class Notifier:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, text: str) -> None: ...


class NullNotifier(Notifier):
    async def start(self) -> None:  # pragma: no cover
        pass

    async def stop(self) -> None:  # pragma: no cover
        pass

    async def send(self, text: str) -> None:  # pragma: no cover
        pass


class TelegramNotifier(Notifier):
    """Adaptateur minimal Telegram → Notifier."""
    def __init__(self, token: Optional[str], chat_id: Optional[str]) -> None:
        self._tg = TelegramAsync(token=token, chat_id=chat_id) if token and chat_id else None
        self._enabled = False

    async def start(self) -> None:
        self._enabled = bool(self._tg and self._tg.enabled())

    async def stop(self) -> None:
        self._enabled = False

    async def send(self, text: str) -> None:
        if self._enabled and self._tg:
            await self._tg.send_message(text)


class CommandStream:
    """
    Expose un flux asynchrone de commandes Telegram (texte brut).
    Usage:
        stream = CommandStream(token, chat_id)
        async for cmd in stream: ...
    """
    def __init__(self, token: Optional[str], chat_id: Optional[str]) -> None:
        self._tg = TelegramAsync(token=token, chat_id=chat_id) if token and chat_id else None
        self._run = False

    async def __aiter__(self) -> AsyncIterator[str]:
        self._run = bool(self._tg and self._tg.enabled())
        while self._run:
            try:
                updates = await self._tg.poll_commands(timeout_s=20) if self._tg else []  # type: ignore
                for u in updates:
                    t = (u.get("text") or "").strip()
                    if t:
                        yield t
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2.0)

    async def stop(self) -> None:
        self._run = False