# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List

Notifier = object                    # doit exposer: async def send(self, msg: str) -> None
CommandStream = Awaitable[str] | asyncio.Queue

async def _sleep_grace(sec: float) -> None:
    try:
        await asyncio.sleep(sec)
    except asyncio.CancelledError:
        raise

async def log_stats_task(
    notifier_getter: Callable[[], Notifier],
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], List[str]],
    period: float = 30.0,
    label: str = "stats",
) -> None:
    while True:
        await _sleep_grace(period)
        try:
            n = ticks_getter()
            syms = symbols_getter()
            pairs = ",".join(syms)
            await notifier_getter().send(f"[{label}] ticks_total={n} (+0 /{int(period)}s) | pairs={pairs}")
        except Exception:
            # ne casse pas la boucle stats si Telegram a un caprice
            pass

@dataclass
class RunConfig:
    timeframe: str = "5m"
    risk_pct: float = 0.05
    symbols_static: List[str] = field(default_factory=list)
    autostart: bool = False

class Orchestrator:
    """
    Orchestrateur léger :
    - PRELAUNCH: prêt, attend /resume
    - RUNNING: 1 tâche par symbole (_live_loop)
    """
    def __init__(
        self,
        exchange,
        config: RunConfig,
        notifier: Notifier,
        command_stream: CommandStream,
        watchlist_factory: Callable[[], "WatchlistManager"],
        csv_cache_dir: str = "data",
    ):
        self.exchange = exchange
        self.config = config
        self.notifier = notifier
        self.command_stream = command_stream
        self.watchlist = watchlist_factory()
        self.csv_cache_dir = csv_cache_dir

        self.state: str = "PRELAUNCH"
        self._symbols: List[str] = []
        self._bg_tasks: List[asyncio.Task] = []
        self._symbol_tasks: Dict[str, asyncio.Task] = {}
        self._ticks_total: int = 0
        self._stop = asyncio.Event()

    # getters pour les tâches
    def ticks_total(self) -> int: return self._ticks_total
    def symbols(self) -> List[str]: return list(self._symbols)

    async def start(self) -> None:
        # 1) boot de la watchlist
        self._symbols = await self._boot_symbols()
        pairs = ",".join(self._symbols)
        await self.notifier.send(
            f"[orchestrator] PRELAUNCH\n[watchlist] boot got: [{pairs}] (tf={self.config.timeframe})"
        )

        # 2) tâches BG: stats + commandes
        self._bg_tasks.append(asyncio.create_task(
            log_stats_task(lambda: self.notifier, self.ticks_total, self.symbols, 30.0, "stats")
        ))
        self._bg_tasks.append(asyncio.create_task(self._command_loop()))

        # 3) autostart éventuel
        if self.config.autostart:
            await self._resume()

        await self.notifier.send(
            "🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live."
        )

    async def run(self) -> None:
        await self._stop.wait()

    async def stop(self) -> None:
        await self._halt_live()
        for t in self._bg_tasks:
            t.cancel()
        self._stop.set()

    async def _command_loop(self) -> None:
        async def _aiter():
            if isinstance(self.command_stream, asyncio.Queue):
                while True:
                    cmd = await self.command_stream.get()
                    yield cmd
            else:
                async for cmd in self.command_stream:
                    yield cmd

        async for raw in _aiter():
            cmd = (raw or "").strip().lower()
            if not cmd:
                continue
            if cmd in {"resume", "/resume"}:
                await self._resume()
            elif cmd in {"stop", "/stop"}:
                await self._halt_live()
                await self.notifier.send("🛑 Arrêt orchestrateur.")
            elif cmd in {"setup", "/setup"}:
                await self.notifier.send("ℹ️ PRELAUNCH: déjà prêt.")
            elif cmd.startswith("/backtest"):
                await self.notifier.send("🧪 Backtest non branché ici (runner séparé).")
            else:
                await self.notifier.send(f"❓Commande inconnue: {cmd}")

    async def _resume(self) -> None:
        if not self._symbols:
            self._symbols = await self._boot_symbols()
        if not self._symbols:
            await self.notifier.send(
                "⚠️ Impossible de démarrer: watchlist vide. Utilise /setup ou configure des symboles."
            )
            return
        if self.state == "RUNNING":
            await self.notifier.send("ℹ️ Déjà en RUNNING.")
            return
        await self._launch_live()
        self.state = "RUNNING"
        await self.notifier.send("🚀 LIVE démarré.")

    async def _launch_live(self) -> None:
        for sym in self._symbols:
            if sym in self._symbol_tasks and not self._symbol_tasks[sym].done():
                continue
            self._symbol_tasks[sym] = asyncio.create_task(self._live_loop(sym))

    async def _halt_live(self) -> None:
        self.state = "PRELAUNCH"
        for t in self._symbol_tasks.values():
            t.cancel()
        self._symbol_tasks.clear()

    async def _boot_symbols(self) -> List[str]:
        try:
            syms = await self.watchlist.boot()
            if syms:
                return syms
        except Exception:
            pass
        if self.config.symbols_static:
            # uniq + conserve l'ordre
            return list(dict.fromkeys(self.config.symbols_static))
        return []

    async def _live_loop(self, symbol: str) -> None:
        tf = self.config.timeframe
        while self.state == "RUNNING":
            try:
                await self.exchange.fetch_ohlcv(symbol, tf, limit=2)
                self._ticks_total += 1
            except Exception as e:
                try:
                    await self.notifier.send(f"[{symbol}] loop error: {e}")
                except Exception:
                    pass
                await _sleep_grace(0.5)
            await _sleep_grace(0.25)

# --- wrapper de compatibilité -------------------------------------------------

async def run_orchestrator(
    exchange,
    config: RunConfig,
    notifier: Notifier,
    watchlist_factory: Callable[[], "WatchlistManager"],
) -> None:
    """
    Compat helper pour l’ancien code qui faisait:
        from scalper.live.orchestrator import run_orchestrator
    et l’appelait avec (exchange, config, notifier, factory).
    """
    orch = Orchestrator(
        exchange=exchange,
        config=config,
        notifier=notifier,
        command_stream=getattr(notifier, "command_stream", asyncio.Queue()),
        watchlist_factory=watchlist_factory,
    )
    await orch.start()
    await orch.run()