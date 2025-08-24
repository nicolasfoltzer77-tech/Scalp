from __future__ import annotations
import asyncio, logging, os
from typing import Any, AsyncIterator, Dict
import requests
log = logging.getLogger("engine.live.notify")

class _NullNotifier:
    async def send(self, text: str) -> None:
        log.info("[NOTIFY] %s", text)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 5.0) -> None:
        self.token, self.chat_id, self.timeout = token, chat_id, timeout
    async def send(self, text: str) -> None:
        url=f"https://api.telegram.org/bot{self.token}/sendMessage"; payload={"chat_id":self.chat_id,"text":text}
        def _post(): requests.post(url, json=payload, timeout=self.timeout)
        await asyncio.get_running_loop().run_in_executor(None, _post)

def build_notifier_and_commands(cfg: Dict[str, Any] | None = None):
    token = os.getenv("TELEGRAM_BOT_TOKEN") or (cfg or {}).get("secrets",{}).get("telegram",{}).get("token")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or (cfg or {}).get("secrets",{}).get("telegram",{}).get("chat_id")
    if token and chat_id: return TelegramNotifier(token, chat_id), None
    return _NullNotifier(), None