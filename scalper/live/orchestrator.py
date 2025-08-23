# scalper/live/orchestrator.py
from __future__ import annotations

import asyncio
import os
import signal
import time
from typing import Any, Dict, List, Optional

from scalper.live.notify import Notifier, CommandStream, build_notifier_and_stream
from scalper.live.commands import CommandHandler
from scalper.live.backtest_telegram import handle_backtest_command
from scalper.live.watchlist import WatchlistManager
from scalper.services.utils import heartbeat_task, log_stats_task
from scalper.exchange.fees import load_bitget_fees
from scalper.signals.factory import load_signal

# --- Logs CSV utilitaires ----------------------------------------------------
import csv
class CsvLog:
    def __init__(self, path: str, headers: List[str]):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.headers = headers
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(headers)
    def write_row(self, row: Dict[str, Any]):
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([row.get(h, "") for h in self.headers])

QUIET = int(os.getenv("QUIET", "0") or "0")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ---------------- Services simples (wrappers vers l'exchange) ----------------
class OhlcvService:
    def __init__(self, exchange): self.exchange = exchange
    async def fetch_once(self, symbol, timeframe="5m", limit=150):
        # Doit renvoyer [[ts,o,h,l,c,v], ...] (ms ou s)
        return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

class OrderService:
    def __init__(self, exchange): self.exchange = exchange
    async def market(self, symbol, side, qty):
        # Renvoie {id, status, ...} selon ton client exchange
        return await self.exchange.create_order(symbol, "market", side, qty)

# ---------------- Trade loop (placeholder) -----------------------------------
class TradeLoop:
    """
    Boucle de trading asynchrone par symbole.
    Remplace par ta version si tu en as déjà une (ex: scalper/live/loops/trade.py).
    """
    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str,
        ohlcv_fetch,
        order_market,
        generate_signal,
        config: Dict[str, Any],
        mode_getter,
        log_signals: CsvLog,
        log_orders: CsvLog,
        log_fills: CsvLog,
        tick_counter_add,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.ohlcv_fetch = ohlcv_fetch
        self.order_market = order_market
        self.generate_signal = generate_signal
        self.config = config
        self.mode_getter = mode_getter
        self.log_signals = log_signals
        self.log_orders = log_orders
        self.log_fills = log_fills
        self._add_ticks = tick_counter_add

    async def run(self, running_getter):
        while running_getter():
            # Pause quand mode != RUNNING
            if self.mode_getter() != "RUNNING":
                await asyncio.sleep(0.5)
                continue

            try:
                ohlcv = await self.ohlcv_fetch(self.symbol, self.timeframe, limit=150)
            except Exception:
                await asyncio.sleep(1.0)
                continue

            # Appelle la stratégie courante
            try:
                sig = self.generate_signal(
                    symbol=self.symbol,
                    ohlcv=ohlcv,
                    equity=self.config.get("cash", 10_000.0),
                    risk_pct=self.config.get("risk_pct", 0.005),
                )
            except Exception:
                await asyncio.sleep(0.5)
                continue

            now = int(time.time() * 1000)
            # Exemple de logging du signal
            if sig:
                self.log_signals.write_row({
                    "ts": now, "symbol": self.symbol, "side": getattr(sig, "side", ""),
                    "entry": getattr(sig, "price", ""), "sl": getattr(sig, "sl", ""),
                    "tp": getattr(sig, "tp", getattr(sig, "tp1", "")), "last": getattr(sig, "last", "")
                })

            self._add_ticks(1)
            await asyncio.sleep(0.2)

# ---------------- Orchestrator -----------------------------------------------
class Orchestrator:
    def __init__(
        self,
        exchange,
        config: Dict[str, Any],
        symbols: Optional[List[str]] = None,
        notifier: Optional[Notifier] = None,
        command_stream: Optional[CommandStream] = None,
    ):
        self.exchange = exchange
        self.config = dict(config)  # {"timeframe","cash","risk_pct","slippage_bps","caps","fees_by_symbol"...}
        self._running = True

        # Sanitizing risk_pct (0..5%)
        val = float(self.config.get("risk_pct", 0.005))
        if val > 0.05:
            if not QUIET:
                print(f"[orchestrator] risk_pct trop élevé ({val}), clamp à 0.05")
            val = 0.05
        if val <= 0.0:
            val = 0.005
        self.config["risk_pct"] = val
        self.config.setdefault("slippage_bps", float(os.getenv("SLIPPAGE_BPS", "0") or "0"))
        self.config.setdefault("caps", {})
        self.config.setdefault("fees_by_symbol", {})

        # État & sélection
        self.mode = "PRELAUNCH"  # PRELAUNCH | RUNNING | PAUSED | STOPPING
        self.selected = {
            "strategy": "current",  # via load_signal()
            "symbols": symbols or [],
            "timeframes": [self.config.get("timeframe", "5m")],
            "risk_pct": self.config["risk_pct"],
        }

        # Notifier / commandes
        self.notifier = notifier
        self.command_stream = command_stream

        # Services
        self.ohlcv = OhlcvService(exchange)
        self.order = OrderService(exchange)

        # Stratégie courante
        self.generate_signal = load_signal(self.selected["strategy"])

        # Watchlist
        self.watchlist = WatchlistManager(
            watchlist_mode=os.getenv("WATCHLIST_MODE", "static"),
            top_candidates=os.getenv("TOP_CANDIDATES", ""),
            local_conc=int(os.getenv("WATCHLIST_LOCAL_CONC", "4") or "4"),
            ohlcv_fetch=self.ohlcv.fetch_once,
        )

        # Symboles/TF actifs
        self.timeframe = self.selected["timeframes"][0]
        self.symbols = list(self.selected["symbols"])

        # Stats
        self._ticks_total = 0
        self._last_hb_ms = int(time.time() * 1000)

        # Logs CSV
        self.log_signals = CsvLog(os.path.join(LOG_DIR, "signals.csv"),
                                  ["ts", "symbol", "side", "entry", "sl", "tp", "last"])
        self.log_orders = CsvLog(os.path.join(LOG_DIR, "orders.csv"),
                                 ["ts", "symbol", "side", "qty", "status", "order_id", "note"])
        self.log_fills = CsvLog(os.path.join(LOG_DIR, "fills.csv"),
                                ["ts", "symbol", "side", "price", "qty", "order_id"])
        self.log_pos = CsvLog(os.path.join(LOG_DIR, "positions.csv"),
                              ["ts", "symbol", "state", "side", "entry", "qty"])
        self.log_wl = CsvLog(os.path.join(LOG_DIR, "watchlist.csv"),
                             ["ts", "mode", "symbols"])

    # ---------------- Helpers état ----------------
    def get_running(self) -> bool: return self._running
    def get_mode(self) -> str: return self.mode
    def _add_ticks(self, n: int):
        self._ticks_total += n
        self._last_hb_ms = int(time.time() * 1000)

    async def stop(self, reason: str = ""):
        self._running = False
        self.mode = "STOPPING"
        if self.notifier:
            try:
                await self.notifier.send(f"🛑 Arrêt orchestrateur. {reason}")
            except Exception:
                pass

    # ---------------- Watchlist / Fees / Positions ----------------
    async def _watchlist_boot(self):
        top = await self.watchlist.boot_topN()
        now = int(time.time() * 1000)
        self.log_wl.write_row({"ts": now, "mode": self.watchlist.mode, "symbols": ",".join(top)})
        if not self.symbols:
            self.symbols = top

    async def _watchlist_refresh(self):
        async for top in self.watchlist.task_auto_refresh():
            now = int(time.time() * 1000)
            self.log_wl.write_row({"ts": now, "mode": self.watchlist.mode, "symbols": ",".join(top)})

    async def _refresh_fees(self):
        """Charge les frais Bitget (maker/taker) par symbole -> config['fees_by_symbol']."""
        if not self.symbols:
            return
        try:
            fees = await load_bitget_fees(self.exchange, self.symbols)
            self.config["fees_by_symbol"] = fees
            if self.notifier:
                txt = ", ".join(f"{s}:{int(f['taker_bps'])}bps" for s, f in fees.items())
                await self.notifier.send("ℹ️ Frais Bitget chargés: " + (txt or "(aucun)"))
        except Exception as e:
            if self.notifier:
                await self.notifier.send(f"⚠️ Impossible de charger les frais Bitget: {e}. Défaut 0 bps.")

    async def _positions_sync(self):
        # Placeholder; branche-le sur tes positions réelles si besoin
        while self.get_running():
            now = int(time.time() * 1000)
            for s in self.symbols:
                self.log_pos.write_row({"ts": now, "symbol": s, "state": "N/A", "side": "N/A", "entry": "", "qty": ""})
            await asyncio.sleep(10.0 if QUIET else 3.0)

    # ---------------- Commandes ----------------
    def _status_snapshot(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "timeframe": self.timeframe,
            "symbols": list(self.symbols),
            "ticks_total": self._ticks_total,
            "hb_age_ms": int(time.time() * 1000) - self._last_hb_ms,
            "strategy": self.selected["strategy"],
            "risk_pct": self.config.get("risk_pct"),
        }

    def _apply_setup_cfg(self, cfg: Dict):
        """
        Appelé par le wizard quand l'utilisateur 'ACCEPTE':
        - met à jour stratégie, symboles, timeframe, risk_pct
        - recharge les frais
        - bascule en RUNNING
        """
        self.selected.update(cfg)
        self.config["risk_pct"] = float(cfg.get("risk_pct", self.config.get("risk_pct", 0.005)))
        self.generate_signal = load_signal(cfg["strategy"])
        self.symbols = list(cfg["symbols"])
        self.timeframe = cfg["timeframes"][0]
        self.mode = "RUNNING"

    # ---------------- Run ----------------
    async def run(self):
        # Notifier/commandes auto si non fournis
        if not self.notifier or not self.command_stream:
            self.notifier, self.command_stream = await build_notifier_and_stream()

        # Signaux OS
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(f"os:{s.name}")))
            except NotImplementedError:
                pass

        # Boot + frais
        await self._watchlist_boot()
        await self._refresh_fees()

        if self.notifier:
            await self.notifier.send("🟢 Orchestrator PRELAUNCH. Utilise /setup ou /backtest. /resume pour démarrer le live.")

        tasks: List[asyncio.Task] = []

        # Heartbeat & stats (respectent QUIET)
        tasks += [
            asyncio.create_task(heartbeat_task(self.get_running, period=15.0)),
            asyncio.create_task(log_stats_task(self.get_running, lambda: self._ticks_total,
                                               lambda: self.symbols, period=30.0)),
        ]

        # Watchlist / Positions
        tasks += [
            asyncio.create_task(self._watchlist_refresh()),
            asyncio.create_task(self._positions_sync()),
        ]

        # Commandes (pause/resume/stop/status/setup/backtest)
        cmd = CommandHandler(
            notifier=self.notifier,
            command_stream=self.command_stream,
            status_getter=self._status_snapshot,
            status_sender=lambda s: None,
        )
        tasks.append(asyncio.create_task(cmd.run(
            on_pause=lambda: setattr(self, "mode", "PAUSED"),
            on_resume=lambda: setattr(self, "mode", "RUNNING"),
            on_stop=lambda: asyncio.create_task(self.stop("telegram:/stop")),
            on_setup_apply=self._apply_setup_cfg,
            on_backtest=lambda tail: handle_backtest_command(
                notifier=self.notifier,
                cmd_tail=tail,
                runtime_config={
                    "top_symbols": self.symbols,
                    "timeframe": self.timeframe,
                    "cash": self.config.get("cash", 10_000),
                    "risk_pct": self.config.get("risk_pct", 0.005),
                    "slippage_bps": self.config.get("slippage_bps", 2.0),
                },
                exchange=self.exchange,   # <<< on passe l'exchange au handler
            )
        )))

        # Boucles trade par symbole (spawn + respawn si modifs)
        trade_tasks: Dict[str, asyncio.Task] = {}

        async def spawn_loops():
            for s in list(self.symbols):
                if s in trade_tasks and not trade_tasks[s].done():
                    continue
                loop_obj = TradeLoop(
                    symbol=s,
                    timeframe=self.timeframe,
                    ohlcv_fetch=self.ohlcv.fetch_once,
                    order_market=self.order.market,
                    generate_signal=self.generate_signal,
                    config=self.config,
                    mode_getter=self.get_mode,
                    log_signals=self.log_signals,
                    log_orders=self.log_orders,
                    log_fills=self.log_fills,
                    tick_counter_add=self._add_ticks,
                )
                trade_tasks[s] = asyncio.create_task(loop_obj.run(self.get_running))

        await spawn_loops()

        async def supervisor():
            """
            Surveille changements (symbols/timeframe/strategy) et respawn les boucles.
            Recharge aussi les frais si la liste de symboles change.
            """
            prev_sig = (tuple(self.symbols), self.timeframe, getattr(self.generate_signal, "__name__", "gen"))
            while self.get_running():
                cur_sig = (tuple(self.symbols), self.timeframe, getattr(self.generate_signal, "__name__", "gen"))
                if cur_sig != prev_sig:
                    if cur_sig[0] != prev_sig[0]:
                        await self._refresh_fees()
                    for t in trade_tasks.values():
                        t.cancel()
                    trade_tasks.clear()
                    await spawn_loops()
                    prev_sig = cur_sig
                await asyncio.sleep(2.0)

        tasks.append(asyncio.create_task(supervisor()))

        try:
            await asyncio.gather(*tasks)
        finally:
            if self.notifier:
                try:
                    await self.notifier.send("🔴 Orchestrator stopped.")
                except Exception:
                    pass

# Entrée pratique (utilisée par bot.py)
async def run_orchestrator(
    exchange,
    config: Dict[str, Any],
    symbols: Optional[List[str]] = None,
    notifier: Optional[Notifier] = None,
    command_stream: Optional[CommandStream] = None,
):
    orch = Orchestrator(exchange, config, symbols, notifier, command_stream)
    await orch.run()