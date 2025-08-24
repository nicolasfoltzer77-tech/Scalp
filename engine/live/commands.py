# engine/live/commands.py
from __future__ import annotations
import asyncio
import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

import requests

log = logging.getLogger("engine.live.commands")


async def telegram_command_stream(
    token: str,
    chat_id: str,
    *,
    poll_secs: int = 5,
    allowed_cmds: Optional[set[str]] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Flux de commandes Telegram via long‑polling.
    Émet des dicts {type: "tg", cmd: "status" | "reload" | "stop" | "help", raw: <update>}
    """
    allowed_cmds = allowed_cmds or {"status", "reload", "stop", "help", "watchlist"}
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    offset = 0

    while True:
        try:
            r = requests.get(url, params={"timeout": poll_secs, "offset": offset + 1}, timeout=poll_secs + 3)
            data = r.json()
            for upd in data.get("result", []):
                offset = upd.get("update_id", offset)
                msg = upd.get("message") or upd.get("edited_message") or {}
                if str(msg.get("chat", {}).get("id")) != str(chat_id):
                    continue
                text = (msg.get("text") or "").strip()
                if not text.startswith("/"):
                    continue
                cmd = text.lstrip("/").split()[0].lower()
                if cmd in allowed_cmds:
                    yield {"type": "tg", "cmd": cmd, "raw": upd}
        except Exception:
            log.debug("poll telegram failed", exc_info=True)
        await asyncio.sleep(poll_secs)


def build_command_stream(cfg: Dict[str, Any] | None = None) -> Optional[AsyncIterator[Dict[str, Any]]]:
    """
    Construit un flux de commandes si TELEGRAM_* sont présents.
    Définir DISABLE_TG_COMMANDS=1 pour désactiver.
    """
    if os.getenv("DISABLE_TG_COMMANDS", "").lower() in {"1", "true", "yes"}:
        return None

    token = os.getenv("TELEGRAM_BOT_TOKEN") or (cfg or {}).get("secrets", {}).get("telegram", {}).get("token")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or (cfg or {}).get("secrets", {}).get("telegram", {}).get("chat_id")
    if token and chat_id:
        return telegram_command_stream(token, chat_id)
    return None