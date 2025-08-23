from __future__ import annotations
import asyncio
import os
from typing import AsyncGenerator, Callable, Optional, Protocol, Tuple, Any

try:
    import aiohttp
except Exception as e:  # noqa: BLE001
    raise RuntimeError("Install aiohttp: pip install aiohttp") from e


class BaseNotifier(Protocol):
    name: str
    async def send(self, text: str) -> None: ...
    async def close(self) -> None: ...


CommandStream = Callable[[], AsyncGenerator[str, None]]


class NullNotifier:
    name = "null"

    async def send(self, text: str) -> None:
        print(f"[notify:null] {text}")

    async def close(self) -> None:
        ...


async def null_command_stream() -> AsyncGenerator[str, None]:
    if False:
        yield ""


class TelegramNotifier:
    """
    Envoi en *texte brut* (aucun parse_mode) pour éviter les erreurs
    'can't parse entities' sur du contenu technique (symboles, underscores, etc.).
    """
    name = "telegram"

    def __init__(self, token: str, chat_id: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)
        self.session = session or aiohttp.ClientSession()
        self._owned = session is None

    async def send(self, text: str) -> None:
        url = f"{self.base}/sendMessage"
        # Plain text, no parse_mode:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
            "disable_notification": False,
        }
        for i in range(3):
            try:
                async with self.session.post(url, json=payload, timeout=15) as r:
                    if r.status == 200:
                        return
                    body = await r.text()
                    raise RuntimeError(f"HTTP {r.status}: {body}")
            except Exception as e:  # noqa: BLE001
                if i == 2:
                    print(f"[notify:telegram] send fail: {e}")
                await asyncio.sleep(1.2 * (i + 1))

    async def commands(self) -> AsyncGenerator[str, None]:
        url = f"{self.base}/getUpdates"
        offset = None
        allowed = {"/setup", "/backtest", "/resume", "/stop"}
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
                    if str(msg.get("chat", {}).get("id")) != self.chat_id:
                        continue
                    text = (msg.get("text") or "").strip()
                    if text and text.split()[0] in allowed:
                        yield text
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2.0)

    async def close(self) -> None:
        if self._owned:
            try:
                await self.session.close()
            except Exception:
                ...


def _env(*names: str, default: Optional[str] = None) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v is not None and str(v).strip() != "":
            return v
    return default


async def build_notifier_and_commands(config: dict[str, Any]) -> Tuple[BaseNotifier, CommandStream]:
    # accepte TELEGRAM_TOKEN/TELEGRAM_CHAT_ID ou TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT
    token = _env("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN", default=config.get("TELEGRAM_TOKEN"))
    chat = _env("TELEGRAM_CHAT_ID", "TELEGRAM_CHAT", default=config.get("TELEGRAM_CHAT_ID"))

    if token and chat:
        try:
            notifier = TelegramNotifier(token=token, chat_id=str(chat))

            async def factory() -> AsyncGenerator[str, None]:
                async for c in notifier.commands():
                    yield c

            print("[notify] Using Telegram notifier/commands")
            # message de pré-lancement en plain text
            asyncio.create_task(
                notifier.send("Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")
            )
            return notifier, factory
        except Exception as e:  # noqa: BLE001
            print(f"[notify] Telegram init failed: {e}. Fallback null.")

    print("[notify] Using Null notifier/commands")
    return NullNotifier(), null_command_stream