# scalper/live/commands.py
from __future__ import annotations

from typing import Awaitable, Callable, Optional


class CommandHandler:
    """
    Gère les commandes reçues d'un CommandStream (Telegram ou Null).
    Chaque commande est routée vers un callback approprié.
    """

    def __init__(self, notifier, command_stream, status_getter, status_sender):
        self.notifier = notifier
        self.stream = command_stream
        self.status_getter = status_getter
        self.status_sender = status_sender

    async def run(
        self,
        on_pause: Callable[[], None],
        on_resume: Callable[[], None],
        on_stop: Callable[[], Awaitable[None]] | None,
        on_setup_apply: Callable[[dict], None],
        on_backtest: Callable[[str], Awaitable[None]] | None = None,
    ):
        """
        Boucle asynchrone qui lit les lignes du CommandStream
        et exécute le callback approprié.
        """
        async for line in self.stream:
            txt = (line or "").strip()
            if not txt:
                continue

            if txt.startswith("/pause"):
                on_pause()
                await self.notifier.send("⏸️ Pause.")

            elif txt.startswith("/resume"):
                on_resume()
                await self.notifier.send("▶️ Resume.")

            elif txt.startswith("/stop"):
                if on_stop:
                    await on_stop()

            elif txt.startswith("/status"):
                snap = self.status_getter()
                await self.notifier.send(f"ℹ️ {snap}")

            elif txt.startswith("/setup"):
                # TODO: appeler ton wizard si tu veux ici
                await self.notifier.send("🧩 Setup wizard à compléter.")

            elif txt.startswith("/backtest"):
                if on_backtest:
                    tail = txt[len("/backtest"):].strip()
                    await on_backtest(tail)
                else:
                    await self.notifier.send("⚠️ Backtest non disponible.")

            else:
                await self.notifier.send(
                    "❓ Commandes: /status /pause /resume /stop /setup /backtest"
                )