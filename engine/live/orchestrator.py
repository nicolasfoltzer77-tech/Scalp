from __future__ import annotations
from dataclasses import dataclass
from typing import List
from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.live.scheduler import Scheduler
from engine.live.state import MarketState
from engine.live.health import HealthBoard

@dataclass
class RunConfig:
    symbols: List[str]
    timeframes: List[str]
    refresh_secs: int
    data_dir: str
    limit: int
    exec_enabled: bool = False
    auto: bool = True
    fresh_mult: float = 1.0
    cooldown_secs: int = 60

def run_config_from_yaml() -> RunConfig:
    cfg = load_config()
    rt = cfg.get("runtime", {}) or {}
    wl = cfg.get("watchlist", {}) or {}
    mt = cfg.get("maintainer", {}) or {}
    auto_cfg = cfg.get("auto") or {}
    wl_doc = load_watchlist()
    syms = [(d.get("symbol") or "").replace("_", "").upper()
            for d in (wl_doc.get("top") or []) if d.get("symbol")] or ["BTCUSDT","ETHUSDT","SOLUSDT"]
    tfs = [str(x) for x in (wl.get("backfill_tfs") or ["1m","5m","15m"])]
    return RunConfig(
        symbols=syms,
        timeframes=tfs,
        refresh_secs=int(mt.get("live_interval_secs", 5)),
        data_dir=str(rt.get("data_dir") or "/notebooks/scalp_data/data"),
        limit=int(wl.get("backfill_limit", 1500)),
        exec_enabled=bool((cfg.get("trading") or {}).get("exec_enabled", False)),
        auto=bool(auto_cfg.get("enabled", True)),
        fresh_mult=float(auto_cfg.get("fresh_mult", mt.get("fresh_mult", 1.0))),
        cooldown_secs=int(auto_cfg.get("cooldown_secs", 60)),
    )

class Orchestrator:
    def __init__(self, cfg: RunConfig, exchange):
        self.cfg = cfg
        self.exchange = exchange
        self.state = MarketState(cfg.symbols, cfg.timeframes, cfg.data_dir, cfg.fresh_mult)
        self.health = HealthBoard(self.state)
        self.sched = Scheduler(interval_sec=max(1, int(cfg.refresh_secs)))

    async def start(self) -> None:
        self.health.banner()
        async for _ in self.sched.ticks():
            await self._step()

    async def step_once(self) -> None:
        await self._step()

    async def _step(self) -> None:
        self.state.refresh()
        self.health.render()
        if self.cfg.auto:
            self.state.auto_actions(limit=self.cfg.limit, cooldown=self.cfg.cooldown_secs)
        for (s, tf) in self.state.ready_pairs():
            pass