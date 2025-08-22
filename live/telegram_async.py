from __future__ import annotations
import time
import requests
import asyncio
from typing import Optional, Dict, Any, List


class TelegramAsync:
    """
    Client Telegram simple basé sur requests, utilisé de manière non bloquante via asyncio.to_thread.
    Sans nouvelle dépendance.
    """
    def __init__(self, token: Optional[str], chat_id: Optional[str]) -> None:
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}" if token else None
        self._offset = 0
        self._enabled = bool(token and chat_id)

    def enabled(self) -> bool:
        return self._enabled

    # ---------- sync I/O (appelées via to_thread) ----------
    def _send_message_sync(self, text: str) -> Dict[str, Any]:
        if not self._enabled:
            return {"ok": False, "reason": "disabled"}
        url = f"{self.base}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}
        try:
            r = requests.post(url, json=payload, timeout=10)
            return r.json()
        except Exception as e:
            return {"ok": False, "error": repr(e)}

    def _get_updates_sync(self, timeout_s: int = 30) -> Dict[str, Any]:
        if not self._enabled:
            return {"ok": True, "result": []}
        url = f"{self.base}/getUpdates"
        params = {"timeout": timeout_s, "offset": self._offset}
        try:
            r = requests.get(url, params=params, timeout=timeout_s + 5)
            return r.json()
        except Exception as e:
            return {"ok": False, "error": repr(e), "result": []}

    # ---------- async wrappers ----------
    async def send_message(self, text: str) -> None:
        await asyncio.to_thread(self._send_message_sync, text)

    async def poll_commands(self, timeout_s: int = 30) -> List[Dict[str, Any]]:
        data = await asyncio.to_thread(self._get_updates_sync, timeout_s)
        if not data.get("ok"):
            return []
        out = []
        for upd in data.get("result", []):
            self._offset = max(self._offset, int(upd.get("update_id", 0)) + 1)
            msg = upd.get("message") or {}
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            out.append({
                "date": msg.get("date"),
                "chat": str((msg.get("chat") or {}).get("id")),
                "text": text,
                "from": (msg.get("from") or {}).get("username") or (msg.get("from") or {}).get("first_name") or "unknown",
            })
        return out
