from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import AsyncIterator, Optional

try:
    import aiohttp
except Exception:  # pragma: no cover
    aiohttp = None


# ============= Notifiers =============

class Notifier:
    async def send(self, text: str) -> None:
        raise NotImplementedError


class NullNotifier(Notifier):
    async def send(self, text: str) -> None:
        if not int(os.getenv("QUIET", "0") or "0"):
            print(text)


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str, session: "aiohttp.ClientSession"):
        self.token = token
        self.chat_id = chat_id
        self.session = session
        self.base = f"https://api.telegram.org/bot{self.token}"

    async def send(self, text: str) -> None:
        url = f"{self.base}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            async with self.session.post(url, json=payload, timeout=30) as r:
                # best effort: on ne lève pas si status != 200
                _ = await r.text()
        except asyncio.CancelledError:
            # En 3.11 CancelledError n'hérite plus d'Exception -> à neutraliser
            return
        except BaseException:
            # On ne casse jamais le flow sur un problème réseau
            return


# ============= Command streams =============

class CommandStream:
    def __aiter__(self) -> AsyncIterator[str]:
        raise NotImplementedError


class NullCommandStream(CommandStream):
    async def __aiter__(self) -> AsyncIterator[str]:
        while True:
            await asyncio.sleep(3600)


@dataclass
class TelegramCommandStream(CommandStream):
    token: str
    chat_id: str
    session: "aiohttp.ClientSession"
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
                        if text.startswith("/"):
                            yield text
            except asyncio.CancelledError:
                break
            except BaseException:
                await asyncio.sleep(self.poll_interval)


# ============= Fabrique =============

async def build_notifier_and_commands() -> tuple[Notifier, CommandStream]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # Permettre de forcer le mode silencieux (ex: machines sans réseau)
    if os.getenv("TELEGRAM_DISABLE") == "1":
        return NullNotifier(), NullCommandStream()

    if token and chat_id and aiohttp is not None:
        session = aiohttp.ClientSession()

        async def _close_on_exit():
            try:
                await asyncio.sleep(0)
            finally:
                try:
                    await session.close()
                except BaseException:
                    pass

        asyncio.create_task(_close_on_exit())
        return TelegramNotifier(token, chat_id, session), TelegramCommandStream(token, chat_id, session)

    return NullNotifier(), NullCommandStream()