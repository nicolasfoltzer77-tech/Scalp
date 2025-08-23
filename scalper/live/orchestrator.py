# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import csv
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from scalper.services.utils import safe_call, heartbeat_task, log_stats_task
from scalper.live.notify import Notifier, CommandStream
from scalper.live.backtest_telegram import handle_backtest_command

# Si tu as un provider de watchlist, importe-le ici (facultatif)
try:
    from scalper.live.watchlist import get_boot_watchlist  # type: ignore
except Exception:  # fallback neutre
    def get_boot_watchlist() -> List[str]:
        return [s.strip().upper() for s in os.getenv("TOP_SYMBOLS", "BTCUSDT,ETHUSDT").split(",") if s.strip()]

QUIET = int(os.getenv("QUIET", "0") or "0")
PRINT_OHLCV_SAMPLE = int(os.getenv("PRINT_OHLCV_SAMPLE", "0") or "0")

LOGS_DIR = Path("scalper/live/logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# CSV utils (mince et suffisant)
# -----------------------------------------------------------------------------
def _csv_writer(path: Path, headers: Iterable[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="") as f:
            csv.writer(f).writerow(headers)

    def append(row: Iterable[Any]):
        with path.open("a", newline="") as f:
            csv.writer(f).writerow(row)

    return append


# -----------------------------------------------------------------------------
# Orchestrateur "fit" : commandes, watchlist, boucles par symbole
# -----------------------------------------------------------------------------
@dataclass
class Orchestrator:
    exchange: Any
    notifier: Notifier
    cmd_stream: CommandStream
    symbols: List[str] = field(default_factory=list)

    running: bool = field(default=False, init=False)
    paused: bool = field(default=False, init=False)
    ticks_total: int = field(default=0, init=False)

    _bg_tasks: List[asyncio.Task] = field(default_factory=list, init=False)
    _per_symbol_tasks: Dict[str, asyncio.Task] = field(default_factory=dict, init=False)

    # CSV writers (créés au boot)
    _w_signals: Any = field(default=None, init=False)
    _w_orders: Any = field(default=None, init=False)
    _w_fills: Any = field(default=None, init=False)
    _w_positions: Any = field(default=None, init=False)
    _w_watchlist: Any = field(default=None, init=False)

    # ---------------- Boot / Stop ----------------
    async def start(self) -> None:
        if self.running:
            return
        self.running = True

        # Watchlist
        if not self.symbols:
            self.symbols = get_boot_watchlist()
        if not QUIET:
            await self.notifier.send(f"[orchestrator] boot watchlist: {self.symbols}")

        # Writers CSV
        self._w_signals   = _csv_writer(LOGS_DIR / "signals.csv",   ["ts","symbol","signal","price"])
        self._w_orders    = _csv_writer(LOGS_DIR / "orders.csv",    ["ts","symbol","side","qty","price","status"])
        self._w_fills     = _csv_writer(LOGS_DIR / "fills.csv",     ["ts","symbol","side","qty","price","fee"])
        self._w_positions = _csv_writer(LOGS_DIR / "positions.csv", ["ts","symbol","qty","avg_price","pnl"])
        self._w_watchlist = _csv_writer(LOGS_DIR / "watchlist.csv", ["ts","symbols"])

        # BG tasks
        self._bg_tasks.append(asyncio.create_task(heartbeat_task(self.notifier, label="orchestrator")))
        self._bg_tasks.append(asyncio.create_task(log_stats_task(self._stats_snapshot)))

        # Boucles par symbole
        for sym in self.symbols:
            self._per_symbol_tasks[sym] = asyncio.create_task(self._symbol_loop(sym))

        # Commandes Telegram
        asyncio.create_task(self._commands_loop())

        if not QUIET:
            await self.notifier.send("[orchestrator] running")

    async def stop(self) -> None:
        if not self.running:
            return
        self.running = False

        # Stop per-symbol tasks
        for t in list(self._per_symbol_tasks.values()):
            t.cancel()
        self._per_symbol_tasks.clear()

        # Stop BG tasks
        for t in list(self._bg_tasks):
            t.cancel()
        self._bg_tasks.clear()

        if not QUIET:
            await self.notifier.send("[orchestrator] stopped")

    # ---------------- Commandes ----------------
    async def _commands_loop(self) -> None:
        async for cmd in self.cmd_stream:
            try:
                if cmd == "/status":
                    await self._handle_status()
                elif cmd == "/pause":
                    await self._handle_pause()
                elif cmd == "/resume":
                    await self._handle_resume()
                elif cmd == "/stop":
                    await self._handle_stop()
                elif cmd.startswith("/backtest"):
                    # déclenche le runner unifié (async en tâche de fond)
                    await handle_backtest_command(cmd, self, self.notifier)
                else:
                    await self.notifier.send(f"Commande inconnue: {cmd}")
            except Exception as e:
                await self.notifier.send(f"Erreur commande: {e}")

    async def _handle_status(self) -> None:
        msg = (
            f"📊 status: running={self.running} paused={self.paused}\n"
            f"symbols={self.symbols}\n"
            f"ticks_total={self.ticks_total}"
        )
        await self.notifier.send(msg)

    async def _handle_pause(self) -> None:
        self.paused = True
        await self.notifier.send("⏸️ Paused")

    async def _handle_resume(self) -> None:
        self.paused = False
        await self.notifier.send("▶️ Resumed")

    async def _handle_stop(self) -> None:
        await self.notifier.send("🛑 Stopping…")
        await self.stop()

    # ---------------- Boucle par symbole ----------------
    async def _symbol_loop(self, symbol: str) -> None:
        """
        Boucle ultra-légère :
        - fetch OHLCV (safe_call)
        - compute signal (generate_signal)
        - log CSV
        - (place order via _maybe_place_order si besoin)
        """
        timeframe = os.getenv("LIVE_TIMEFRAME", "5m")
        limit = int(os.getenv("LIVE_LIMIT", "200"))

        while self.running:
            try:
                if self.paused:
                    await asyncio.sleep(0.5)
                    continue

                ohlcv = await safe_call(
                    self.exchange.fetch_ohlcv, label=f"ohlcv:{symbol}",
                    symbol=symbol, timeframe=timeframe, limit=limit
                )

                if not ohlcv:
                    await asyncio.sleep(0.2); continue

                # format attendu : [[ts,o,h,l,c,v], ...]
                last_ts, _, _, _, last_close, _ = ohlcv[-1]
                sig = self._generate_signal(symbol, ohlcv)

                if PRINT_OHLCV_SAMPLE and not QUIET:
                    await self.notifier.send(f"[{symbol}] last={last_close} sig={sig}")

                # log signal
                self._w_signals([last_ts, symbol, sig, last_close])
                self.ticks_total += 1

                # ici tu peux brancher le Risk Manager / FSM / Orders
                await self._maybe_place_order(symbol, sig, last_close)

                await asyncio.sleep(0)  # yield
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not QUIET:
                    await self.notifier.send(f"[{symbol}] loop error: {e}")
                await asyncio.sleep(0.5)

    # ---------------- Hooks trading (stubs minces) ----------------
    def _generate_signal(self, symbol: str, ohlcv: List[List[float]]) -> str:
        """
        Place-holder (remplacer par ta factory de stratégies live) :
        retourne 'BUY' | 'SELL' | 'HOLD'
        """
        # Exemple hyper-simple: croisement close vs moyenne des 10 dernières
        closes = [r[4] for r in ohlcv[-10:]] if len(ohlcv) >= 10 else [r[4] for r in ohlcv]
        if not closes:
            return "HOLD"
        avg = sum(closes) / len(closes)
        last = closes[-1]
        if last > avg * 1.002:
            return "BUY"
        if last < avg * 0.998:
            return "SELL"
        return "HOLD"

    async def _maybe_place_order(self, symbol: str, signal: str, price: float) -> None:
        """
        Stub : branche ton OrderExecutor ici.
        On se contente de logger pour rester mince.
        """
        ts = self._now_ms()
        if signal == "BUY":
            self._w_orders([ts, symbol, "buy", 0, price, "skipped"])
        elif signal == "SELL":
            self._w_orders([ts, symbol, "sell", 0, price, "skipped"])

    # ---------------- Stats / Heartbeat ----------------
    def _stats_snapshot(self) -> Dict[str, Any]:
        return {
            "ticks_total": self.ticks_total,
            "pairs": len(self.symbols),
            "running": self.running,
            "paused": self.paused,
        }

    @staticmethod
    def _now_ms() -> int:
        return int(asyncio.get_event_loop().time() * 1000)