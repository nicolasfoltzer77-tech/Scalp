# scalp/live/orchestrator.py
from __future__ import annotations
import asyncio, os, time, signal
from typing import Any, Dict, List, Optional

from ..services.utils import heartbeat_task, log_stats_task
from .notify import Notifier, CommandStream, build_notifier_and_stream
from .watchlist import WatchlistManager
from .loops.trade import TradeLoop
from .commands import CommandHandler
from .logs import CsvLog
from ..signals.factory import load_signal
from ..exchange.fees import load_bitget_fees

QUIET = int(os.getenv("QUIET", "0") or "0")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ---------------- Services simples (wrappers vers l'exchange) ----------------
class OhlcvService:
    def __init__(self, exchange): self.exchange = exchange
    async def fetch_once(self, symbol, timeframe="5m", limit=150):
        # Doit renvoyer [[ts,o,h,l,c,v], ...]
        return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

class OrderService:
    def __init__(self, exchange): self.exchange = exchange
    async def market(self, symbol, side, qty):
        # Renvoie {id, status, ...} selon ton client exchange
        return await self.exchange.create_order(symbol, "market", side, qty)

# ---------------- Orchestrator (maigre) ----------------
class Orchestrator:
    def __init__(self, exchange, config: Dict[str, Any], symbols: Optional[List[str]] = None,
                 notifier: Optional[Notifier] = None, command_stream: Optional[CommandStream] = None):
        self.exchange = exchange
        self.config = dict(config)  # ex: {"timeframe":"5m","cash":10000, ...}
        self._running = True

        # État d’exécution
        self.mode = "PRELAUNCH"  # PRELAUNCH | RUNNING | PAUSED | STOPPING
        self.selected = {
            "strategy": "current",
            "symbols": symbols or [],
            "timeframes": [self.config.get("timeframe", "5m")],
            "risk_pct": float(self.config.get("risk_pct", 0.5)),
        }
        # Defaults Risk/Frais/Slippage/Caps
        self.config.setdefault("risk_pct", self.selected["risk_pct"])
        self.config.setdefault("slippage_bps", float(os.getenv("SLIPPAGE_BPS", "0") or "0"))
        self.config.setdefault("caps", {})                 # {"BTCUSDT": {"min_qty":..., "min_notional":...}}
        self.config.setdefault("fees_by_symbol", {})      # rempli au boot via Bitget

        # Notifier / commandes
        self.notifier = notifier
        self.command_stream = command_stream

        # Services
        self.ohlcv = OhlcvService(exchange)
        self.order = OrderService(exchange)

        # Stratégie
        self.generate_signal = load_signal(self.selected["strategy"])

        # Watchlist
        self.watchlist = WatchlistManager(
            watchlist_mode=os.getenv("WATCHLIST_MODE","static"),
            top_candidates=os.getenv("TOP_CANDIDATES",""),
            local_conc=int(os.getenv("WATCHLIST_LOCAL_CONC","4") or "4"),
            ohlcv_fetch=self.ohlcv.fetch_once,
        )

        # Symboles actifs
        self.timeframe = self.selected["timeframes"][0]
        self.symbols = list(self.selected["symbols"])

        # Stats
        self._ticks_total = 0
        self._last_heartbeat_ms = int(time.time()*1000)

        # Logs CSV
        self.log_signals = CsvLog(os.path.join(LOG_DIR,"signals.csv"),   ["ts","symbol","side","entry","sl","tp","last"])
        self.log_orders  = CsvLog(os.path.join(LOG_DIR,"orders.csv"),    ["ts","symbol","side","qty","status","order_id","note"])
        self.log_fills   = CsvLog(os.path.join(LOG_DIR,"fills.csv"),     ["ts","symbol","side","price","qty","order_id"])
        self.log_pos     = CsvLog(os.path.join(LOG_DIR,"positions.csv"), ["ts","symbol","state","side","entry","qty"])
        self.log_wl      = CsvLog(os.path.join(LOG_DIR,"watchlist.csv"), ["ts","mode","symbols"])

    # ---------------- Helpers état ----------------
    def get_running(self) -> bool: return self._running
    def get_mode(self) -> str: return self.mode
    def _add_ticks(self, n: int):
        self._ticks_total += n
        self._last_heartbeat_ms = int(time.time()*1000)

    async def stop(self, reason: str=""):
        self._running = False
        self.mode = "STOPPING"
        if self.notifier:
            try: await self.notifier.send(f"🛑 Arrêt orchestrateur. {reason}")
            except: pass

    # ---------------- Watchlist / Fees / Positions ----------------
    async def _watchlist_boot(self):
        top = await self.watchlist.boot_topN()
        now = int(time.time()*1000)
        self.log_wl.write_row({"ts": now, "mode": self.watchlist.mode, "symbols": ",".join(top)})
        if not self.symbols:
            self.symbols = top

    async def _watchlist_refresh(self):
        async for top in self.watchlist.task_auto_refresh():
            now = int(time.time()*1000)
            self.log_wl.write_row({"ts": now, "mode": self.watchlist.mode, "symbols": ",".join(top)})

    async def _refresh_fees(self):
        """Charge les frais Bitget (maker/taker) par symbole et pousse dans config['fees_by_symbol']."""
        if not self.symbols:
            return
        try:
            fees = await load_bitget_fees(self.exchange, self.symbols)
            self.config["fees_by_symbol"] = fees
            if self.notifier:
                txt = ", ".join(f"{s}:{int(f['taker_bps'])}bps" for s,f in fees.items())
                await self.notifier.send("ℹ️ Frais Bitget (taker) chargés: " + (txt or "(aucun)"))
        except Exception as e:
            if self.notifier:
                await self.notifier.send(f"⚠️ Impossible de charger les frais Bitget: {e}. Utilisation 0 bps par défaut.")

    async def _positions_sync(self):
        while self.get_running():
            now = int(time.time()*1000)
            # Placeholder : rapprochement réel à brancher
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
            "hb_age_ms": int(time.time()*1000) - self._last_heartbeat_ms,
            "strategy": self.selected["strategy"],
        }

    def _apply_setup_cfg(self, cfg: Dict):
        """
        Appelé quand l'utilisateur 'ACCEPTE' depuis le wizard:
        - met à jour stratégie, symboles, timeframe, risk_pct
        - re-charge les frais
        - bascule en RUNNING
        """
        self.selected.update(cfg)
        self.config["risk_pct"] = float(cfg.get("risk_pct", self.config["risk_pct"]))
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
            await self.notifier.send("🟢 Orchestrator PRELAUNCH. Utilise /setup pour valider avant trading.")

        tasks: List[asyncio.Task] = []

        # Heartbeat & stats (respectent QUIET)
        tasks += [
            asyncio.create_task(heartbeat_task(self.get_running, period=15.0)),
            asyncio.create_task(log_stats_task(self.get_running, lambda: self._ticks_total, lambda: self.symbols, period=30.0)),
        ]

        # Watchlist / Positions
        tasks += [
            asyncio.create_task(self._watchlist_refresh()),
            asyncio.create_task(self._positions_sync()),
        ]

        # Commandes (wizard + pause/resume/stop/status)
        cmd = CommandHandler(
            notifier=self.notifier, command_stream=self.command_stream,
            status_getter=self._status_snapshot, status_sender=lambda s: None,
        )
        tasks.append(asyncio.create_task(cmd.run(
            on_pause=lambda: setattr(self, "mode", "PAUSED"),
            on_resume=lambda: setattr(self, "mode", "RUNNING"),
            on_stop=lambda: asyncio.create_task(self.stop("telegram:/stop")),
            on_setup_apply=self._apply_setup_cfg
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
                    config=self.config,                         # contient risk_pct, caps, slippage_bps, fees_by_symbol
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
            prev_sig = (tuple(self.symbols), self.timeframe, self.generate_signal.__name__)
            while self.get_running():
                cur_sig = (tuple(self.symbols), self.timeframe, self.generate_signal.__name__)
                if cur_sig != prev_sig:
                    # (Re)charge frais si symboles changés
                    if cur_sig[0] != prev_sig[0]:
                        await self._refresh_fees()
                    # Respawn boucles
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
                try: await self.notifier.send("🔴 Orchestrator stopped.")
                except: pass

# Entrée pratique (utilisée par bot.py)
async def run_orchestrator(exchange, config: Dict[str, Any], symbols: Optional[List[str]] = None,
                           notifier: Optional[Notifier] = None, command_stream: Optional[CommandStream] = None):
    orch = Orchestrator(exchange, config, symbols, notifier, command_stream)
    await orch.run()