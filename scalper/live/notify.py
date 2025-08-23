# scalper/live/notify.py
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import aiohttp

QUIET = int(os.getenv("QUIET", "0") or "0")


# =============================== Notifier API ================================

class Notifier:
    """Interface simple pour l'envoi de notifications."""
    async def send(self, text: str) -> None: ...
    async def send_document(self, path: os.PathLike | str, caption: str = "") -> None:
        """Optionnel: envoi d'un fichier (implémenté par TelegramNotifier)."""
        return


class NullNotifier(Notifier):
    """Console fallback si Telegram est désactivé/non configuré."""
    async def send(self, text: str) -> None:
        if not QUIET:
            print(f"[notify] {text}", flush=True)

    async def send_document(self, path: os.PathLike | str, caption: str = "") -> None:
        if not QUIET:
            print(f"[notify-doc] {caption} -> {path}", flush=True)


class TelegramNotifier(Notifier):
    """Notifier Telegram minimal (sendMessage / sendDocument)."""

    def __init__(self, token: str, chat_id: str, timeout: float = 15.0):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)
        self.timeout = float(timeout)

    async def _post_json(self, session: aiohttp.ClientSession, url: str, payload: dict) -> dict:
        for attempt in range(5):
            try:
                async with session.post(url, json=payload, timeout=self.timeout) as resp:
                    data = await resp.json(content_type=None)
                    if not data.get("ok", False):
                        raise RuntimeError(f"Telegram error: {data}")
                    return data
            except Exception as e:
                await asyncio.sleep(min(2 ** attempt, 10))
                if attempt == 4:
                    raise e

    async def send(self, text: str) -> None:
        async with aiohttp.ClientSession(raise_for_status=False) as s:
            await self._post_json(
                s,
                f"{self.base}/sendMessage",
                {"chat_id": self.chat_id, "text": text},
            )

    async def send_document(self, path: os.PathLike | str, caption: str = "") -> None:
        p = str(path)
        data = {"chat_id": self.chat_id, "caption": caption}
        for attempt in range(5):
            try:
                async with aiohttp.ClientSession(raise_for_status=False) as s:
                    form = aiohttp.FormData()
                    for k, v in data.items():
                        form.add_field(k, str(v))
                    with open(p, "rb") as f:
                        form.add_field(
                            "document",
                            f,
                            filename=os.path.basename(p),
                            content_type="application/octet-stream",
                        )
                        async with s.post(f"{self.base}/sendDocument", data=form, timeout=self.timeout) as resp:
                            # Telegram renvoie du JSON
                            try:
                                payload = await resp.json(content_type=None)
                            except Exception:
                                payload = {"ok": False, "raw": await resp.text()}
                            if not payload.get("ok", False):
                                raise RuntimeError(f"Telegram error: {payload}")
                            return
            except Exception:
                await asyncio.sleep(min(2 ** attempt, 10))
                if attempt == 4:
                    raise


# ============================== Command Stream ===============================

class CommandStream:
    """Interface d'un flux de commandes (async iterator de str)."""
    def __aiter__(self) -> AsyncIterator[str]:
        return self._aiter()

    async def _aiter(self) -> AsyncIterator[str]:
        if False:  # pragma: no cover
            yield ""


class NullCommandStream(CommandStream):
    """Ne produit jamais aucun message (mode silencieux / pas de Telegram)."""
    async def _aiter(self) -> AsyncIterator[str]:
        while True:
            await asyncio.sleep(3600)


@dataclass
class _UpdateOffset:
    value: int = 0


class TelegramCommandStream(CommandStream):
    """
    Long-polling Telegram: lit getUpdates et renvoie le texte des messages
    provenant du chat_id configuré. Ne gère que les messages texte.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        poll_timeout: int = 20,
        session_timeout: float = 25.0,
        allowed_prefixes: tuple[str, ...] = ("/",),
    ):
        self.base = f"https://api.telegram.org/bot{token}"
        self.chat_id = str(chat_id)
        self.poll_timeout = int(poll_timeout)
        self.session_timeout = float(session_timeout)
        self.allowed_prefixes = allowed_prefixes
        self._offset = _UpdateOffset(0)
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    async def _fetch(self) -> list[dict]:
        """Appelle getUpdates (long polling) et renvoie la liste d'updates."""
        params = {
            "timeout": self.poll_timeout,
            "offset": self._offset.value + 1 if self._offset.value else None,
        }
        # Nettoyage None
        params = {k: v for k, v in params.items() if v is not None}

        for attempt in range(6):
            try:
                async with aiohttp.ClientSession(raise_for_status=False) as s:
                    async with s.get(
                        f"{self.base}/getUpdates",
                        params=params,
                        timeout=self.session_timeout,
                    ) as resp:
                        data = await resp.json(content_type=None)
                        if not data.get("ok", False):
                            # Peut arriver si token invalide
                            raise RuntimeError(f"getUpdates error: {data}")
                        return data.get("result", []) or []
            except Exception as e:
                # backoff + limite
                await asyncio.sleep(min(2 ** attempt, 15))
                if attempt == 5:
                    if not QUIET:
                        print(f"[telegram] getUpdates failed: {e}", flush=True)
                    return []

    async def _aiter(self) -> AsyncIterator[str]:
        while not self._stop:
            updates = await self._fetch()
            for u in updates:
                try:
                    uid = int(u.get("update_id", 0))
                    if uid > self._offset.value:
                        self._offset.value = uid
                except Exception:
                    pass

                # On ne s'intéresse qu'aux messages texte adressés à notre chat_id
                msg = u.get("message") or u.get("edited_message")
                if not msg:
                    continue
                chat = msg.get("chat") or {}
                if str(chat.get("id")) != self.chat_id:
                    # message dans un autre chat
                    continue
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                # Optionnel: filtrer pour ne laisser passer que des commandes /...
                if self.allowed_prefixes and not text.startswith(self.allowed_prefixes):
                    # Laisse passer quand même ? Ici on filtre (commandes seulement)
                    # continue
                    pass
                yield text

            # Pause courte entre deux polls (en cas de batch vide, le long-polling a déjà attendu)
            await asyncio.sleep(0.2)


# =========================== Factory (build helpers) ==========================

async def build_notifier_and_stream() -> tuple[Notifier, CommandStream]:
    """
    Construit (Notifier, CommandStream) en fonction des variables d'environnement :
      - TELEGRAM_BOT_TOKEN
      - TELEGRAM_CHAT_ID
    Si absents → Null* (console only).
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if token and chat_id:
        if not QUIET:
            print("[notify] Using Telegram notifier/commands", flush=True)
        n = TelegramNotifier(token=token, chat_id=chat_id)
        s = TelegramCommandStream(token=token, chat_id=chat_id)
        return n, s

    if not QUIET:
        print("[notify] Using NullNotifier/NullCommandStream (Telegram off)", flush=True)
    return NullNotifier(), NullCommandStream()