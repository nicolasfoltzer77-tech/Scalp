# scalper/live/notify.py
from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncGenerator, Callable, Optional, Protocol, Tuple

try:
    import aiohttp
except Exception as e:  # noqa: BLE001
    raise RuntimeError(
        "Le module 'aiohttp' est requis pour Telegram. Installe-le via 'pip install aiohttp'."
    ) from e


# ===== Types exportés pour l'orchestrateur =====
class BaseNotifier(Protocol):
    name: str
    async def send(self, text: str) -> None: ...
    async def close(self) -> None: ...

# Fabrique de flux de commandes asynchrones (sans argument)
CommandStream = Callable[[], AsyncGenerator[str, None]]


# ===== Fallback "Null" =====
class NullNotifier:
    name = "null"
    async def send(self, text: str) -> None:
        print(f"[notify:null] {text}")
    async def close(self) -> None:
        pass

async def null_command_stream() -> AsyncGenerator[str, None]:
    if False:  # pragma: no cover
        yield ""


# ===== Telegram notifier + polling léger =====
class TelegramNotifier:
    name = "telegram"

    def __init__(self, token: str, chat_id: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.session = session or aiohttp.ClientSession()
        self._owned_session = session is None

    async def send(self, text: str) -> None:
        url = f"{self.base}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        for attempt in range(3):
            try:
                async with self.session.post(url, json=payload, timeout=15) as r:
                    if r.status == 200:
                        return
                    body = await r.text()
                    raise RuntimeError(f"HTTP {r.status}: {body}")
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"[notify:telegram] send fail: {e}")
                else:
                    await asyncio.sleep(1.5 * (attempt + 1))

    async def commands(self, *, allowed: Optional[set[str]] = None) -> AsyncGenerator[str, None]:
        url = f"{self.base}/getUpdates"
        offset = None
        allowed_set = allowed or {"/setup", "/backtest", "/resume", "/stop"}
        while True:
            try:
                params = {"timeout": 20}
                if offset is not None:
                    params["offset"] = offset
                async with self.session.get(url, params=params, timeout=25) as r:
                    data = await r.json()
                if not data.get("ok"):
                    await asyncio.sleep(2.0)
                    continue
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or upd.get("edited_message")
                    if not msg:
                        continue
                    if str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                        continue
                    text = (msg.get("text") or "").strip()
                    if text and text.split()[0] in allowed_set:
                        yield text
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2.0)

    async def close(self) -> None:
        if self._owned_session:
            try:
                await self.session.close()
            except Exception:
                pass


# ===== Fabrique : Telegram si possible, sinon Null =====
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name, default)
    return v if (v is not None and str(v).strip() != "") else None


async def build_notifier_and_commands(
    config: dict[str, Any]
) -> Tuple[BaseNotifier, CommandStream]:
    token = _env("TELEGRAM_TOKEN") or config.get("TELEGRAM_TOKEN")
    chat = _env("TELEGRAM_CHAT_ID") or config.get("TELEGRAM_CHAT_ID")

    if token and chat:
        try:
            notifier = TelegramNotifier(token=token, chat_id=str(chat))
            async def factory() -> AsyncGenerator[str, None]:
                async for cmd in notifier.commands():
                    yield cmd
            asyncio.create_task(
                notifier.send("🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")
            )
            print("[notify] Using Telegram notifier/commands")
            return notifier, factory
        except Exception as e:  # noqa: BLE001
            print(f"[notify] Telegram init failed: {e} -> fallback to Null")

    print("[notify] Using Null notifier/commands")
    return NullNotifier(), null_command_stream