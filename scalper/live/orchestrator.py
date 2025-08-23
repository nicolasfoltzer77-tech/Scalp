# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Iterable, List, Optional

# Types légers pour notifier & commandes
Notifier = object  # doit implémenter: async def send(self, msg: str) -> None
CommandStream = Awaitable[str] | asyncio.Queue  # une queue d'events "str"

# --- Utils petits & purs ------------------------------------------------------

async def _sleep_grace(sec: float) -> None:
    try:
        await asyncio.sleep(sec)
    except asyncio.CancelledError:
        raise

# log stats périodiques (déporté ici pour être simple)
async def log_stats_task(
    notifier_getter: Callable[[], Notifier],
    ticks_getter: Callable[[], int],
    symbols_getter: Callable[[], List[str]],
    period: float = 30.0,
    label: str = "stats",
) -> None:
    while True:
        await _sleep_grace(period)
        n = ticks_getter()
        syms = symbols_getter()
        pairs = ",".join(syms)
        try:
            await notifier_getter().send(f"[{label}] ticks_total={n} (+0 /{int(period)}s) | pairs={pairs}")
        except Exception:
            # on ne tue pas la boucle stats si Telegram a un caprice
            pass

# --- Orchestrateur ------------------------------------------------------------

@dataclass
class RunConfig:
    timeframe: str = "5m"
    risk_pct: float = 0.05
    symbols_static: List[str] = field(default_factory=list)  # fallback si WL vide
    autostart: bool = False  # pour démarrer directement en RUNNING

class Orchestrator:
    """
    Orchestrateur léger :
    - PRELAUNCH: prêt, attend /resume
    - RUNNING: crée 1 tâche par symbole (boucle "live_loop")
    """
    def __init__(
        self,
        exchange,                # objet bourse (doit fournir fetch_ohlcv ou équivalent)
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

    # --- Getters utilisés par les tâches
    def ticks_total(self) -> int: return self._ticks_total
    def symbols(self) -> List[str]: return list(self._symbols)

    # --- Boot / commandes / cycle état

    async def start(self) -> None:
        # 1) Boot watchlist
        self._symbols = await self._boot_symbols()
        pairs = ",".join(self._symbols)
        await self.notifier.send(f"[orchestrator] PRELAUNCH\n[watchlist] boot got: [{pairs}] (tf={self.config.timeframe})")

        # 2) Tâches d'arrière-plan
        self._bg_tasks.append(asyncio.create_task(
            log_stats_task(lambda: self.notifier, self.ticks_total, self.symbols, period=30.0, label="stats")
        ))
        self._bg_tasks.append(asyncio.create_task(self._command_loop()))
        # 3) Autostart éventuel
        if self.config.autostart:
            await self._resume()

        await self.notifier.send("🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")

    async def run(self) -> None:
        # garde le process en vie tant qu'on n'a pas stop
        await self._stop.wait()

    async def stop(self) -> None:
        # stop global
        await self._halt_live()
        for t in self._bg_tasks:
            t.cancel()
        self._stop.set()

    # --- Commandes Telegram
    async def _command_loop(self) -> None:
        """
        Consomme les commandes ('resume', 'stop', 'setup', 'backtest'…).
        """
        # Le command_stream est soit une Queue, soit un awaitable (générateur async)
        async def _aiter():
            if isinstance(self.command_stream, asyncio.Queue):
                while True:
                    cmd = await self.command_stream.get()
                    yield cmd
            else:
                # stream asynchrone "aiterable"
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

    # --- États

    async def _resume(self) -> None:
        if not self._symbols:
            # tente de rebooter la WL avant de refuser
            self._symbols = await self._boot_symbols()
        if not self._symbols:
            await self.notifier.send("⚠️ Impossible de démarrer: watchlist vide. Utilise /setup ou configure des symboles.")
            return
        if self.state == "RUNNING":
            await self.notifier.send("ℹ️ Déjà en RUNNING.")
            return
        await self._launch_live()
        self.state = "RUNNING"
        await self.notifier.send("🚀 LIVE démarré.")

    async def _launch_live(self) -> None:
        # crée 1 tâche par symbole
        for sym in self._symbols:
            if sym in self._symbol_tasks and not self._symbol_tasks[sym].done():
                continue
            self._symbol_tasks[sym] = asyncio.create_task(self._live_loop(sym))

    async def _halt_live(self) -> None:
        self.state = "PRELAUNCH"
        for t in self._symbol_tasks.values():
            t.cancel()
        self._symbol_tasks.clear()

    # --- Watchlist & warmup

    async def _boot_symbols(self) -> List[str]:
        """
        1) Tente la watchlist
        2) Sinon le fallback statique
        3) Sinon []
        """
        try:
            syms = await self.watchlist.boot()
            if syms:
                return syms
        except Exception:
            pass
        if self.config.symbols_static:
            return list(dict.fromkeys(self.config.symbols_static))  # uniq, preserve order
        return []

    # --- Boucle par symbole

    async def _live_loop(self, symbol: str) -> None:
        """
        Boucle simple: fetch OHLCV via exchange/cache, évalue la stratégie, compte les ticks.
        Ici on ne place pas d'ordres: on veut d'abord valider le flux & les stats.
        """
        tf = self.config.timeframe
        while self.state == "RUNNING":
            try:
                # 1) Fetch OHLCV (éventuellement via ton cache CSV sur disque)
                # Doit être non-bloquant (ton exchange adapté est asynchrone dans le repo)
                await self.exchange.fetch_ohlcv(symbol, tf, limit=2)  # ne garde pas le résultat ici
                # 2) Ticks ++
                self._ticks_total += 1
            except Exception as e:
                try:
                    await self.notifier.send(f"[{symbol}] loop error: {e}")
                except Exception:
                    pass
                # on évite le spin
                await _sleep_grace(0.5)
            # cadence
            await _sleep_grace(0.25)