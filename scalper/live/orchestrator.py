# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Optional, Tuple

# Services utilitaires (déjà présents dans le repo)
from scalper.services.utils import heartbeat_task, log_stats_task

# Système de notifications/commandes
# NOTE: build_notifier_and_commands attend "config" en paramètre -> on lui passe self.config
from scalper.live.notify import build_notifier_and_commands


# ---------------------------------------------------------------------
# Types légers
# ---------------------------------------------------------------------
SendFn = Callable[[str], Awaitable[None]]
CommandStream = Iterable[Awaitable[str]]  # async generator dans l’implémentation réelle


@dataclass
class RunConfig:
    """Boîte à clés minimaliste pour le run.
    On accepte un dict-like en entrée, on l'enrobe pour l'accès par .get().
    """
    data: dict

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def timeframe(self) -> str:
        return self.get("timeframe", "5m")

    @property
    def risk_pct(self) -> float:
        # clamp ailleurs si besoin
        return float(self.get("risk_pct", 0.05))

    @property
    def symbols(self) -> list[str]:
        syms = self.get("symbols") or self.get("watchlist") or []
        if isinstance(syms, str):
            # "BTCUSDT,ETHUSDT" -> ["BTCUSDT","ETHUSDT"]
            syms = [s.strip() for s in syms.split(",") if s.strip()]
        return list(syms)


# ---------------------------------------------------------------------
# Orchestrateur
# ---------------------------------------------------------------------
class Orchestrator:
    """Boucle de pré-lancement + hooks commandes Telegram.
    - Warmup cache (fait côté bot avant la construction)
    - Heartbeat + stats périodiques
    - Consommation de /setup /backtest /resume /stop
    """

    def __init__(
        self,
        exchange: Any,
        config: dict | RunConfig,
        notifier: Optional[Any] = None,
        command_stream: Optional[Any] = None,
    ) -> None:
        self.exchange = exchange
        self.config = config if isinstance(config, RunConfig) else RunConfig(config)
        self.notifier = notifier
        self.command_stream = command_stream

        # état simple
        self._running = False
        self._bg_tasks: list[asyncio.Task] = []
        self._ticks_total: int = 0
        self._symbols: list[str] = self.config.symbols or []

    # --------- getters pour les tasks background ---------
    @property
    def running(self) -> bool:
        return self._running

    def ticks_total(self) -> int:
        return self._ticks_total

    def symbols(self) -> list[str]:
        return list(self._symbols)

    async def _send(self, msg: str) -> None:
        if not self.notifier:
            return
        try:
            await self.notifier.send(msg)
        except Exception as e:  # garde‑fou: jamais planter la boucle pour un send
            print(f"[notify] send fail: {e!r}")

    # -----------------------------------------------------------------
    # Cycle de vie
    # -----------------------------------------------------------------
    async def start(self) -> None:
        """Prépare le notifier & démarre le PRELAUNCH + tâches background."""
        # ⚠️ Correction ici : on passe bien self.config à build_notifier_and_commands
        if not self.notifier or not self.command_stream:
            self.notifier, self.command_stream = await build_notifier_and_commands(self.config)

        await self._send("🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")

        self._running = True

        # Tâche heartbeat (toutes les 30s par défaut dans utils.heartbeat_task)
        self._bg_tasks.append(asyncio.create_task(heartbeat_task(lambda: self._running, self.notifier)))
        # Tâche logs de stats (ticks_total & symbols), toutes les 30s
        self._bg_tasks.append(
            asyncio.create_task(log_stats_task(lambda: self._ticks_total, lambda: self._symbols))
        )

    async def stop(self) -> None:
        """Arrête proprement l’orchestrateur et ses tâches."""
        if not self._running:
            return

        self._running = False
        for t in self._bg_tasks:
            t.cancel()
        self._bg_tasks.clear()
        await self._send("🛑 Arrêt orchestrateur.")

    async def run(self) -> None:
        """Boucle de pré‑lancement : on écoute les commandes, on garde le heartbeat/metrics."""
        await self.start()
        try:
            # Consommation du flux de commandes (async generator)
            async for cmd in self.command_stream:
                await self._handle_command(cmd)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    # -----------------------------------------------------------------
    # Commandes
    # -----------------------------------------------------------------
    async def _handle_command(self, cmd: str) -> None:
        cmd = (cmd or "").strip()
        if not cmd:
            return

        if cmd.startswith("/stop"):
            await self._send("🛑 Stop demandé.")
            await self.stop()
            return

        if cmd.startswith("/setup"):
            await self._send("ℹ️ PRELAUNCH: déjà prêt.")
            return

        if cmd.startswith("/resume"):
            # Ici ton démarrage live réel (non branché dans ce prélaunch)
            await self._send("ℹ️ PRELAUNCH: déjà prêt.")
            return

        if cmd.startswith("/backtest"):
            # Backtest géré par un runner séparé -> simple message
            await self._send("🧪 Backtest non branché ici (runner séparé).")
            return

        # Commande inconnue => echo help court
        await self._send("❓ Commande inconnue. Utilise /setup, /backtest, /resume ou /stop.")

    # -----------------------------------------------------------------
    # Hooks pour incrémenter les ticks (appelés ailleurs dans le code live)
    # -----------------------------------------------------------------
    def on_tick_batch(self, n: int, symbols_snapshot: Optional[Iterable[str]] = None) -> None:
        """Appelle cette méthode depuis ta boucle de marché pour tracer les stats."""
        try:
            self._ticks_total += int(n)
        except Exception:
            pass
        if symbols_snapshot:
            self._symbols = list(symbols_snapshot)


# ---------------------------------------------------------------------
# API module‑level (utilisée par bot.py)
# ---------------------------------------------------------------------
async def run_orchestrator(
    exchange: Any,
    cfg: dict | RunConfig,
    notifier: Optional[Any] = None,
    factory: Optional[Any] = None,  # réservé si tu veux brancher une fabrique plus tard
) -> None:
    """Point d’entrée simple, utilisé par bot.py."""
    orch = Orchestrator(exchange=exchange, config=cfg, notifier=notifier, command_stream=None)
    await orch.run()


# ---------------------------------------------------------------------
# Petit main pour tests manuels (optionnel)
# ---------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    async def _demo():
        class DummyExchange:
            pass

        await run_orchestrator(DummyExchange(), {"symbols": ["BTCUSDT", "ETHUSDT"], "timeframe": "5m"})

    asyncio.run(_demo())