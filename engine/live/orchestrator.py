# engine/live/orchestrator.py
from __future__ import annotations
from typing import Dict, List, Optional
from .scheduler import Scheduler
from .state import MarketState
from .health import HealthBoard
from engine.signals.factory import resolve_signal_fn

class RunConfig:
    def __init__(self, symbols: List[str], timeframes: List[str], exec_enabled: bool):
        self.symbols = symbols
        self.timeframes = timeframes
        self.exec_enabled = exec_enabled

class Orchestrator:
    def __init__(self, cfg: RunConfig, exchange, strategies_cfg: Dict):
        self.cfg = cfg
        self.exchange = exchange
        self.state = MarketState(cfg.symbols, cfg.timeframes)
        self.health = HealthBoard(self.state)
        self.scheduler = Scheduler(interval_sec=2)

    async def start(self) -> None:
        self.health.banner()
        async for tick in self.scheduler.ticks():
            await self._step()

    async def _step(self) -> None:
        # 1) rafraîchir état (fraîcheur OHLCV + présence stratégies)
        self.state.refresh()
        self.health.render()             # TUI simple (tableau MIS/OLD/DAT/OK)

        # 2) sélectionner ce qui est “OK” pour signaux
        for symbol, tf in self.state.ready_pairs():
            sig_fn = resolve_signal_fn(symbol, tf)
            signal = sig_fn(self.exchange, symbol, tf)
            # 3) si exec_enabled, dispatcher vers executor (non-couplé ici)