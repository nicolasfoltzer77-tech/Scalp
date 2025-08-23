# scalper/live/notify.py
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import AsyncIterator, Optional

try:
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None  # on gèrera le fallback au NullNotifier/NullCommandStream


# ============= Notifiers =============

class Notifier:
    async def send(self, text: str) -> None:
        raise NotImplementedError


class NullNotifier(Notifier):
    async def send(self, text: str) -> None:
        # Silence si QUIET=1, sinon print
        if not int(os.getenv("QUIET", "0") or "0"):
            print(text)


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str, session: aiohttp.ClientSession):
        self.token = token
        self.chat_id = chat_id
        self.session = session
        self.base = f"https://api.telegram.org/bot{self.token}"

    async def send(self, text: str) -> None:
        try:
            url = f"{self.base}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text}
            async with self.session.post(url, json=payload, timeout=30) as r:
                if r.status != 200:
                    # on ne lève pas: on reste best-effort
                    pass
        except Exception:
            pass


# ============= Command streams =============

class CommandStream:
    """Interface commune pour un flux de commandes (async iterator)."""
    def __aiter__(self) -> AsyncIterator[str]:
        raise NotImplementedError


class NullCommandStream(CommandStream):
    async def __aiter__(self) -> AsyncIterator[str]:
        # ne renvoie jamais de commandes
        while True:
            await asyncio.sleep(3600)
            if False:  # pragma: no cover
                yield ""


@dataclass
class TelegramCommandStream(CommandStream):
    token: str
    chat_id: str
    session: aiohttp.ClientSession
    poll_interval: float = 1.0

    async def __aiter__(self) -> AsyncIterator[str]:
        base = f"https://api.telegram.org/bot{self.token}"
        offset: Optional[int] = None
        while True:
            try:
                params = {"timeout": 30}
                if offset is not None:
                    params["offset"] = offset
                async with self.session.get(f"{base}/getUpdates", params=params, timeout=35) as r:
                    if r.status != 200:
                        await asyncio.sleep(self.poll_interval)
                        continue
                    data = await r.json()
                    for upd in data.get("result", []):
                        offset = upd["update_id"] + 1
                        msg = upd.get("message") or upd.get("edited_message") or {}
                        if str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                            continue
                        text = (msg.get("text") or "").strip()
                        if not text:
                            continue
                        # on ne garde que les commandes /xxx
                        if text.startswith("/"):
                            yield text
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.poll_interval)


# ============= Fabrique =============

async def build_notifier_and_commands() -> tuple[Notifier, CommandStream]:
    """
    Retourne (notifier, command_stream).
    - Si TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID présents -> TelegramNotifier + TelegramCommandStream
    - Sinon -> NullNotifier + NullCommandStream
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id and aiohttp is not None:
        # session unique partagée par notifier & command stream
        session = aiohttp.ClientSession()
        notifier = TelegramNotifier(token, chat_id, session)

        # petit hook de shutdown propre quand le programme s'arrête
        async def _close_session_on_exit():
            try:
                await asyncio.sleep(0)  # placeholder
            finally:
                try:
                    await session.close()
                except Exception:
                    pass
        # on attache une tâche de fond pour garantir la fermeture
        asyncio.create_task(_close_session_on_exit())

        return notifier, TelegramCommandStream(token, chat_id, session)
    else:
        # Fallback silencieux
        return NullNotifier(), NullCommandStream()