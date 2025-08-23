# -*- coding: utf-8 -*-
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, AsyncIterator

from scalper.hooks.prewarm_cache import prewarm_cache


@dataclass
class RunConfig:
    symbols: List[str] = field(default_factory=lambda: [
        "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
        "DOGEUSDT","ADAUSDT","LTCUSDT","AVAXUSDT","LINKUSDT"
    ])
    timeframe: str = "5m"
    refresh_secs: float = 30.0
    cache_dir: str = "/notebooks/data"
    # Tu peux ajouter d'autres paramètres ici (risques, stratégie, etc.)


class Orchestrator:
    def __init__(self, cfg: RunConfig, notifier, cache_dir_factory: Optional[Callable[[], str]] = None):
        self.cfg = cfg
        self.notifier = notifier
        self._cache_dir_factory = cache_dir_factory
        self._bg_tasks: list[asyncio.Task] = []
        self._ticks_total: int = 0
        self._running: bool = False

    # --- getters exposés aux tâches de log/heartbeat
    def ticks_total(self) -> int:
        return self._ticks_total

    def symbols(self) -> List[str]:
        return list(self.cfg.symbols)

    async def _heartbeat_task(self) -> None:
        while self._running:
            try:
                await self.notifier.send("heartbeat alive")
            finally:
                await asyncio.sleep(30)

    async def _log_stats_task(self) -> None:
        # log toutes les 30s
        while self._running:
            try:
                msg = f"[stats] ticks_total={self._ticks_total} (+0 /30s) | pairs={','.join(self.cfg.symbols) if self.cfg.symbols else ''}"
                await self.notifier.send(msg)
            finally:
                await asyncio.sleep(30)

    async def _main_loop(self) -> None:
        """Boucle principale ultra‑simple qui incrémente un compteur."""
        refresh = max(2.0, float(self.cfg.refresh_secs))
        while self._running:
            # Ici tu brancheras fetch_ohlcv / signaux / stratégies
            self._ticks_total += len(self.cfg.symbols)
            await asyncio.sleep(refresh)

    async def start(self) -> None:
        # Pré‑chauffe cache (non bloquant et robuste)
        prewarm_cache(
            cfg={},  # placeholder
            symbols=self.cfg.symbols,
            timeframe=self.cfg.timeframe,
            out_dir=(self._cache_dir_factory() if self._cache_dir_factory else self.cfg.cache_dir),
        )
        await self.notifier.send("🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")

        self._running = True
        self._bg_tasks.append(asyncio.create_task(self._heartbeat_task()))
        self._bg_tasks.append(asyncio.create_task(self._log_stats_task()))
        try:
            await self._main_loop()
        finally:
            # arrêt propre
            self._running = False
            for t in self._bg_tasks:
                t.cancel()
            self._bg_tasks.clear()

    async def run(self) -> None:
        await self.start()


async def run_orchestrator(cfg: RunConfig, notifier, cache_dir_factory: Optional[Callable[[], str]] = None) -> None:
    """Entrée unique utilisée par bot.py"""
    orch = Orchestrator(cfg, notifier, cache_dir_factory)
    await orch.run()