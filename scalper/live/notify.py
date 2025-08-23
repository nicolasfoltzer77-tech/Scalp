# scalper/live/notify.py
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Optional, AsyncIterator

try:
    # util commun (retry + respect QUIET)
    from scalper.services.utils import safe_call  # type: ignore
except Exception:
    # fallback minimal si absent
    async def safe_call(fn, label: str = "task", max_retry: int = 3, base_delay: float = 0.5):
        attempt = 0
        last_exc = None
        while attempt <= max_retry:
            try:
                return await fn()
            except Exception as e:  # noqa
                last_exc = e
                attempt += 1
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
        raise last_exc  # type: ignore

import aiohttp


# -------------------------
# Notifiers
# -------------------------

class Notifier:
    """Interface minimale de notification."""
    async def send(self, text: str) -> None: ...
    async def close(self) -> None: ...


class NullNotifier(Notifier):
    def __init__(self, quiet: bool = False):
        self.quiet = quiet

    async def send(self, text: str) -> None:
        if not self.quiet:
            print(f"[notify:null] {text}")

    async def close(self) -> None:
        pass


@dataclass
class _TgCfg:
    token: str
    chat_id: str
    timeout: float = 15.0
    base_url: str = "https://api.telegram.org"


class TelegramNotifier(Notifier):
    """Notifier Telegram très simple via HTTP Bot API."""

    def __init__(self, cfg: _TgCfg, quiet: bool = False):
        self.cfg = cfg
        self.quiet = quiet
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.cfg.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def send(self, text: str) -> None:
        async def _send():
            sess = await self._ensure_session()
            url = f"{self.cfg.base_url}/bot{self.cfg.token}/sendMessage"
            payload = {"chat_id": self.cfg.chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
            async with sess.post(url, json=payload) as r:
                if r.status != 200:
                    body = await r.text()
                    raise RuntimeError(f"telegram send failed: HTTP {r.status} {body[:200]}")
        await safe_call(_send, label="telegram.send", max_retry=2, base_delay=0.7)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# -------------------------
# Commandes Telegram (polling)
# -------------------------

class CommandStream:
    """Poller basique des updates Telegram → file de commandes texte."""
    def __init__(self, cfg: _TgCfg, poll_interval: float = 1.5):
        self.cfg = cfg
        self.poll_interval = poll_interval
        self._session: Optional[aiohttp.ClientSession] = None
        self._q: asyncio.Queue[str] = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._offset = 0  # update_id offset

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _loop(self):
        self._running = True
        while self._running:
            try:
                sess = await self._ensure_session()
                url = f"{self.cfg.base_url}/bot{self.cfg.token}/getUpdates"
                params = {"timeout": 15, "offset": self._offset}
                async with sess.get(url, params=params) as r:
                    if r.status != 200:
                        await asyncio.sleep(self.poll_interval)
                        continue
                    data = await r.json()
                    if not data.get("ok"):
                        await asyncio.sleep(self.poll_interval)
                        continue
                    for upd in data.get("result", []):
                        self._offset = max(self._offset, upd.get("update_id", 0) + 1)
                        msg = upd.get("message") or upd.get("edited_message") or {}
                        chat = str(((msg.get("chat") or {}).get("id")) or "")
                        if chat != self.cfg.chat_id:
                            continue  # ignorer autres chats
                        txt = (msg.get("text") or "").strip()
                        if txt:
                            await self._q.put(txt)
                await asyncio.sleep(self.poll_interval)
            except Exception:
                await asyncio.sleep(self.poll_interval)

    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aiter__(self) -> AsyncIterator[str]:
        while True:
            cmd = await self._q.get()
            yield cmd


# -------------------------
# Fabrique / bootstrap
# -------------------------

def _env_bool(name: str, default: str = "1") -> bool:
    return (os.getenv(name, default) or "").strip() not in ("0", "false", "False", "no", "NO")

async def build_notifier_and_commands() -> tuple[Notifier, Optional[CommandStream], str]:
    """
    Construit (Notifier, CommandStream, status_text).
    - Si TELEGRAM_TOKEN/CHAT_ID manquent OU si l'API est injoignable → NullNotifier et None pour le stream.
    """
    quiet = _env_bool("QUIET", "0")
    if not _env_bool("TELEGRAM_ENABLED", "1"):
        return NullNotifier(quiet=quiet), None, "telegram disabled"

    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return NullNotifier(quiet=quiet), None, "telegram env missing (TELEGRAM_TOKEN/TELEGRAM_CHAT_ID)"

    cfg = _TgCfg(token=token, chat_id=chat_id)
    tg = TelegramNotifier(cfg, quiet=quiet)
    stream = CommandStream(cfg)

    # Sanity check non bloquant : on essaye un send() très court
    try:
        await asyncio.wait_for(tg.send("🟢 Bot en démarrage…"), timeout=8)
        await stream.start()
        return tg, stream, "telegram ok"
    except Exception as e:
        # bascule en NullNotifier, le live continue
        await tg.close()
        return NullNotifier(quiet=quiet), None, f"telegram fallback: {e}"