# scalper/live/notify.py
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional, Tuple

from scalper.live.telegram_async import TelegramNotifier, TelegramCommandStream


@dataclass
class NullNotifier:
    async def send(self, _text: str) -> None:
        return None


@dataclass
class NullCommandStream:
    async def __aiter__(self) -> AsyncIterator[Any]:  # pragma: no cover
        if False:
            yield None

    # legacy: some code accidentally calls the stream; keep it harmless
    def __call__(self) -> "NullCommandStream":
        return self


async def build_notifier_and_commands(config: Optional[dict] = None) -> Tuple[Any, Any]:
    """
    Returns (notifier, command_stream). Chooses Telegram if env vars are present,
    otherwise no‑op implementations.

    Kept async because TelegramCommandStream may open a session.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        notifier = TelegramNotifier(token=token, chat_id=chat_id)
        commands = TelegramCommandStream(token=token, chat_id=chat_id)
        # tiny probe so we fail fast if token is invalid
        try:
            await notifier.send("🔵 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")
        except Exception:
            # fall back to null but don't crash the bot
            notifier = NullNotifier()
            commands = NullCommandStream()
        return notifier, commands

    return NullNotifier(), NullCommandStream()