# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable, Optional, AsyncIterator

from scalper.services.utils import heartbeat_task, log_stats_task
from scalper.live.notify import build_notifier_and_commands


@dataclass
class RunConfig:
    data: dict

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def timeframe(self) -> str:
        return self.get("timeframe", "5m")

    @property
    def risk_pct(self) -> float:
        return float(self.get("risk_pct", 0.05))

    @property
    def symbols(self) -> list[str]:
        syms = self.get("symbols") or self.get("watchlist") or []
        if isinstance(syms, str):
            syms = [s.strip() for s in syms.split(",") if s.strip()]
        return list(syms)


class Orchestrator:
    def __init__(
        self,
        exchange: Any,
        config: dict | RunConfig,
        notifier: Optional[Any] = None,
        command_stream: Optional[AsyncIterator[str]] = None,
    ) -> None:
        self.exchange = exchange
        self.config = config if isinstance(config, RunConfig) else RunConfig(config)
        self.notifier = notifier
        self.command_stream = command_stream

        self._running: bool = False
        self._bg_tasks: list[asyncio.Task] = []
        self._ticks_total: int = 0
        self._symbols: list[str] = self.config.symbols or []

    # getters pour bg tasks
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
        except Exception as e:
            print(f"[notify] send fail: {e!r}")

    async def start(self) -> None:
        if not self.notifier or not self.command_stream:
            self.notifier, self.command_stream = await build_notifier_and_commands(self.config)

        self._running = True
        # tâches de fond (signatures corrigées)
        self._bg_tasks.append(asyncio.create_task(heartbeat_task(self.running, self.notifier)))
        self._bg_tasks.append(
            asyncio.create_task(
                log_stats_task(self.notifier, self.ticks_total, self.symbols)
            )
        )

        await self._send(
            "🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live."
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for t in self._bg_tasks:
            t.cancel()
        self._bg_tasks.clear()
        await self._send("🛑 Arrêt orchestrateur.")

    async def run(self) -> None:
        await self.start()
        try:
            async for cmd in self.command_stream:  # stream nul = tick toutes les heures
                await self._handle_command(cmd)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

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
            await self._send("ℹ️ PRELAUNCH: déjà prêt.")
            return
        if cmd.startswith("/backtest"):
            await self._send("🧪 Backtest non branché ici (runner séparé).")
            return
        await self._send("❓ Commande inconnue. Utilise /setup, /backtest, /resume ou /stop.")

    def on_tick_batch(self, n: int, symbols_snapshot: Optional[Iterable[str]] = None) -> None:
        try:
            self._ticks_total += int(n)
        except Exception:
            pass
        if symbols_snapshot:
            self._symbols = list(symbols_snapshot)


async def run_orchestrator(
    exchange: Any,
    cfg: dict | RunConfig,
    notifier: Optional[Any] = None,
    factory: Optional[Any] = None,
) -> None:
    orch = Orchestrator(exchange=exchange, config=cfg, notifier=notifier, command_stream=None)
    await orch.run()