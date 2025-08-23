# scalper/live/commands.py
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class CommandHandler:
    """
    Gère les commandes reçues d'un CommandStream (Telegram ou Null).
    Chaque commande est routée vers un callback approprié.
    Les erreurs de callbacks sont capturées pour ne pas tuer l'orchestrateur.
    """

    def __init__(self, notifier, command_stream, status_getter, status_sender):
        self.notifier = notifier
        self.stream = command_stream
        self.status_getter = status_getter
        self.status_sender = status_sender

    async def _safe_call(self, coro: Awaitable[None], err_msg: str) -> None:
        try:
            await coro
        except Exception as e:
            try:
                await self.notifier.send(f"⚠️ {err_msg}: {e}")
            except Exception:
                pass  # on ne propage jamais

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
        TOUTE exception de callback est absorbée pour ne pas terminer cette task.
        """
        async for line in self.stream:
            txt = (line or "").strip()
            if not txt:
                continue

            try:
                if txt.startswith("/pause"):
                    on_pause()
                    await self.notifier.send("⏸️ Pause.")

                elif txt.startswith("/resume"):
                    on_resume()
                    await self.notifier.send("▶️ Resume.")

                elif txt.startswith("/stop"):
                    if on_stop:
                        await self._safe_call(on_stop(), "Arrêt échoué")

                elif txt.startswith("/status"):
                    snap = self.status_getter()
                    await self.notifier.send(f"ℹ️ {snap}")

                elif txt.startswith("/setup"):
                    await self.notifier.send("🧩 Setup wizard à compléter.")

                elif txt.startswith("/backtest"):
                    if on_backtest:
                        tail = txt[len("/backtest"):].strip()
                        # IMPORTANT : on ne bloque PAS la boucle de commandes.
                        asyncio.create_task(self._safe_call(
                            on_backtest(tail), "Backtest échoué"
                        ))
                        await self.notifier.send("🧪 Backtest lancé en tâche de fond.")
                    else:
                        await self.notifier.send("⚠️ Backtest non disponible.")

                else:
                    await self.notifier.send(
                        "❓ Commandes: /status /pause /resume /stop /setup /backtest"
                    )

            except Exception as e:
                # On protège la boucle quoi qu'il arrive
                try:
                    await self.notifier.send(f"⚠️ Erreur commande: {e}")
                except Exception:
                    pass