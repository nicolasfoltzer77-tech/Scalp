# scalp/live/orchestrator.py
from __future__ import annotations

import asyncio
import csv
import os
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Tuple

from ..services.utils import safe_call, heartbeat_task, log_stats_task
from .notify import Notifier, CommandStream, build_notifier_and_stream
from .watchlist import WatchlistManager
from ..signals.factory import load_signal
from ..backtest.cli import fetch_ohlcv_sync  # à brancher sur ta source historique
from .setup_wizard import SetupWizard

# -----------------------------------------------------------------------------
# Config globale
# -----------------------------------------------------------------------------
QUIET = int(os.getenv("QUIET", "0") or "0")
PRINT_OHLCV_SAMPLE = int(os.getenv("PRINT_OHLCV_SAMPLE", "0") or "0")

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Utilitaires de log CSV minimalistes
# -----------------------------------------------------------------------------

class _CsvLog:
    def __init__(self, path: str, headers: List[str]):
        self.path = path
        self.headers = headers
        self._ensure_header()

    def _ensure_header(self):
        must_write = not os.path.exists(self.path) or os.path.getsize(self.path) == 0
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if must_write:
            with open(self.path, "w", newline="") as f:
                csv.writer(f).writerow(self.headers)

    def write_row(self, row: Dict[str, Any]):
        with open(self.path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.headers)
            w.writerow({k: row.get(k, "") for k in self.headers})

# -----------------------------------------------------------------------------
# Abstractions très légères pour les services de marché (à adapter à ton repo)
# -----------------------------------------------------------------------------

class OhlcvService:
    """Wrappe l'exchange pour fetch l'OHLCV d'un symbole/timeframe."""
    def __init__(self, exchange):
        self.exchange = exchange

    async def fetch_once(self, symbol: str, timeframe: str = "5m", limit: int = 150) -> List[List[float]]:
        # doit retourner [[ts, o, h, l, c, v], ...]
        return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

class OrderService:
    """Interface simplifiée vers l'exchange pour passer des ordres (à adapter)."""
    def __init__(self, exchange):
        self.exchange = exchange

    async def place_market(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        # Adapte au client Bitget/CCXT : retourne un dict avec id, status, price, filled, etc.
        return await self.exchange.create_order(symbol, "market", side, qty)

class PositionFSM:
    """FSM minimaliste pour positions par symbole (à étendre selon ton impl)."""
    def __init__(self):
        self.state = "FLAT"  # FLAT | OPEN
        self.entry = 0.0
        self.qty = 0.0
        self.side = "flat"

    def can_open(self) -> bool:
        return self.state == "FLAT"

    def on_open(self, side: str, entry: float, qty: float):
        self.state = "OPEN"; self.side = side; self.entry = entry; self.qty = qty

    def can_close(self) -> bool:
        return self.state == "OPEN"

    def on_close(self):
        self.state = "FLAT"; self.side = "flat"; self.entry = 0.0; self.qty = 0.0

# -----------------------------------------------------------------------------
# Orchestrateur
# -----------------------------------------------------------------------------

@dataclass
class SymbolContext:
    symbol: str
    timeframe: str
    ohlcv: List[List[float]] = field(default_factory=list)
    ticks: int = 0
    fsm: PositionFSM = field(default_factory=PositionFSM)

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
        self.config = config
        self._running = True

        # Mode de vie / contrôle
        self.mode = "PRELAUNCH"  # PRELAUNCH | RUNNING | PAUSED | STOPPING
        self.selected = {"strategy": "current", "symbols": symbols or [], "timeframes": [], "risk_pct": 0.5}

        # Notifier / commandes
        self.notifier = notifier
        self.command_stream = command_stream

        # Services
        self.ohlcv_service = OhlcvService(exchange)
        self.order_service = OrderService(exchange)

        # Stratégie (factory, remplaçable via /setup)
        self.generate_signal: Callable[[List[List[float]], Dict[str, Any]], Dict[str, Any]] = load_signal(
            self.selected["strategy"]
        )

        # Watchlist
        self.watchlist = WatchlistManager(
            watchlist_mode=os.getenv("WATCHLIST_MODE", "static"),
            top_candidates=os.getenv("TOP_CANDIDATES", ""),
            local_conc=int(os.getenv("WATCHLIST_LOCAL_CONC", "4") or "4"),
            ohlcv_fetch=self.ohlcv_service.fetch_once,
        )

        # Contexte par symbole (initialement vide; sera rempli au boot watchlist)
        self.timeframe = self.config.get("timeframe", "5m")
        base_symbols = symbols or []
        self.symbol_contexts: Dict[str, SymbolContext] = {
            s: SymbolContext(symbol=s, timeframe=self.timeframe) for s in base_symbols
        }

        # Stats
        self._ticks_total = 0
        self._last_heartbeat_ms = int(time.time() * 1000)

        # Logs CSV
        self.log_signals = _CsvLog(os.path.join(LOG_DIR, "signals.csv"),
                                   ["ts","symbol","side","entry","sl","tp","last"])
        self.log_orders  = _CsvLog(os.path.join(LOG_DIR, "orders.csv"),
                                   ["ts","symbol","side","qty","status","order_id","note"])
        self.log_fills   = _CsvLog(os.path.join(LOG_DIR, "fills.csv"),
                                   ["ts","symbol","side","price","qty","order_id"])
        self.log_pos     = _CsvLog(os.path.join(LOG_DIR, "positions.csv"),
                                   ["ts","symbol","state","side","entry","qty"])
        self.log_wl      = _CsvLog(os.path.join(LOG_DIR, "watchlist.csv"),
                                   ["ts","mode","symbols"])

    # -------------------------------------------------------------------------
    # Cycle de vie
    # -------------------------------------------------------------------------
    def get_running(self) -> bool:
        return self._running

    async def stop(self, reason: str = ""):
        self._running = False
        self.mode = "STOPPING"
        if self.notifier:
            try:
                await self.notifier.send(f"🛑 Arrêt orchestrateur. {reason}")
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Tâches secondaires
    # -------------------------------------------------------------------------
    async def _task_commands(self):
        """Gestion des commandes Telegram (ou autre backend)."""
        if not self.command_stream:
            return
        if self.notifier:
            await self.notifier.send("Commandes: /setup /status /pause /resume /stop")

        async for text in self.command_stream:
            cmd = (text or "").strip().lower()
            if cmd == "/status":
                await self._cmd_status()
                continue

            if cmd == "/pause":
                if self.mode == "RUNNING":
                    self.mode = "PAUSED"
                if self.notifier: await self.notifier.send("⏸️ Paused")
                continue

            if cmd == "/resume":
                self.mode = "RUNNING"
                if self.notifier: await self.notifier.send("▶️ Running")
                continue

            if cmd == "/stop":
                if self.notifier: await self.notifier.send("🛑 Stop demandé")
                await self.stop("telegram:/stop")
                return

            if cmd == "/setup":
                await self._cmd_setup()
                continue

            # commandes non reconnues
            if self.notifier:
                await self.notifier.send("Commande inconnue. Utilise /setup /status /pause /resume /stop")

    async def _cmd_status(self):
        hb_age = int(time.time() * 1000) - self._last_heartbeat_ms
        symbols = ",".join(sorted(self.symbol_contexts.keys())) or "(aucun)"
        msg = (
            f"mode={self.mode} | timeframe={self.timeframe}\n"
            f"symbols={symbols}\n"
            f"ticks_total={self._ticks_total} | heartbeat_age_ms={hb_age}"
        )
        if self.notifier:
            await self.notifier.send(msg)

    async def _cmd_setup(self):
        """Wizard + backtest, puis application si accepté."""
        if not self.notifier or not self.command_stream:
            return
        default_syms = list(self.symbol_contexts.keys()) or ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT"]
        default_tfs = ["5m","15m","1h","4h"]
        wiz = SetupWizard(self.notifier, self.command_stream, fetch_ohlcv_sync, out_dir="out_bt_setup")
        res = await wiz.run(default_syms, default_tfs, default_strategy=self.selected["strategy"])
        if res.accepted:
            # Applique la config
            self.selected = {"strategy": res.strategy, "symbols": res.symbols,
                             "timeframes": res.timeframes, "risk_pct": res.risk_pct}
            # Rechargement stratégie
            self.generate_signal = load_signal(res.strategy)
            # Mise à jour des symboles / contexts
            self.symbol_contexts = {s: SymbolContext(symbol=s, timeframe=res.timeframes[0]) for s in res.symbols}
            self.timeframe = res.timeframes[0]
            # Bascule en RUNNING directement (ou laisse /resume si tu préfères)
            self.mode = "RUNNING"
            if self.notifier:
                await self.notifier.send("✅ Configuration appliquée. Démarrage du trading (RUNNING).")
        else:
            self.mode = "PRELAUNCH"
            if self.notifier:
                await self.notifier.send("ℹ️ Setup annulé. Le bot reste en PRELAUNCH.")

    async def _task_watchlist_boot(self):
        """Boot de la watchlist (écrit dans watchlist.csv)."""
        top = await self.watchlist.boot_topN()
        now = int(time.time()*1000)
        self.log_wl.write_row({"ts": now, "mode": self.watchlist.mode, "symbols": ",".join(top)})
        # Si aucun symbole fourni, utilise ceux de la watchlist
        if not self.symbol_contexts:
            self.symbol_contexts = {s: SymbolContext(symbol=s, timeframe=self.timeframe) for s in top}

    async def _task_watchlist_refresh(self):
        """Rafraîchissement périodique de la watchlist (sans changer les boucles en cours)."""
        async for top in self.watchlist.task_auto_refresh():
            now = int(time.time()*1000)
            self.log_wl.write_row({"ts": now, "mode": self.watchlist.mode, "symbols": ",".join(top)})

    async def _task_positions_sync(self):
        """Exemple de tâche de rapprochement positions (à adapter selon ton repo)."""
        while self.get_running():
            # Ici tu peux rapprocher open_positions exchange ↔ FSM et logguer positions.csv
            now = int(time.time()*1000)
            for s, ctx in self.symbol_contexts.items():
                self.log_pos.write_row({
                    "ts": now, "symbol": s, "state": ctx.fsm.state, "side": ctx.fsm.side,
                    "entry": ctx.fsm.entry, "qty": ctx.fsm.qty
                })
            await asyncio.sleep(10.0 if QUIET else 3.0)

    # -------------------------------------------------------------------------
    # Boucles de trading
    # -------------------------------------------------------------------------
    async def _task_trade_loop(self, symbol: str):
        """Boucle principale par symbole : fetch OHLCV → signal → éventuellement ordre."""
        timeframe = self.timeframe
        ctx = self.symbol_contexts[symbol]
        lookback = 200
        while self.get_running():
            # Garde PRELAUNCH/PAUSED
            if self.mode != "RUNNING":
                await asyncio.sleep(0.5)
                continue

            async def _fetch():
                return await self.ohlcv_service.fetch_once(symbol, timeframe=timeframe, limit=lookback+2)

            ohlcv = await safe_call(_fetch, label=f"fetch_ohlcv:{symbol}")
            if not ohlcv or len(ohlcv) < lookback+1:
                await asyncio.sleep(1.0)
                continue

            ctx.ohlcv = ohlcv
            ctx.ticks += 1
            self._ticks_total += 1
            self._last_heartbeat_ms = int(time.time()*1000)

            window = ohlcv[-(lookback+1):]  # liste de [ts,o,h,l,c,v]
            ts, _o, _h, _l, c, _v = window[-1]

            # Appel stratégie
            try:
                sig = self.generate_signal(window, self.config) or {}
            except Exception as e:
                if not QUIET:
                    print(f"[orchestrator] generate_signal error {symbol}: {e}", flush=True)
                await asyncio.sleep(0.5)
                continue

            side = sig.get("side", "flat")
            entry = sig.get("entry", c)
            sl = sig.get("sl"); tp = sig.get("tp")

            # Log signal
            self.log_signals.write_row({"ts": ts, "symbol": symbol, "side": side, "entry": entry, "sl": sl, "tp": tp, "last": c})

            # Trading rules simples (à adapter à ton RiskManager et OrderExecutor)
            if ctx.fsm.state == "FLAT" and side in ("long","short"):
                # sizing trivial: risk_pct du solde → qty notionnelle / prix
                balance = self.config.get("cash", 10_000.0)
                risk_pct = float(self.selected.get("risk_pct", 0.5))
                notionnel = max(0.0, balance * risk_pct)
                qty = max(0.0, notionnel / max(entry or c, 1e-9))
                if qty > 0:
                    async def _place():
                        return await self.order_service.place_market(symbol, side, qty)
                    order = await safe_call(_place, label=f"order:{symbol}")
                    ctx.fsm.on_open(side, entry or c, qty)
                    self.log_orders.write_row({"ts": ts, "symbol": symbol, "side": side, "qty": qty,
                                               "status": "placed", "order_id": order.get("id") if order else "", "note": "entry"})
            elif ctx.fsm.state == "OPEN":
                # Sortie sur signal flat/opposé (gestion SL/TP à implémenter si besoin)
                if side == "flat" or (side in ("long","short") and side != ctx.fsm.side):
                    exit_side = "sell" if ctx.fsm.side == "long" else "buy"
                    qty = ctx.fsm.qty
                    async def _close():
                        return await self.order_service.place_market(symbol, exit_side, qty)
                    order = await safe_call(_close, label=f"close:{symbol}")
                    self.log_orders.write_row({"ts": ts, "symbol": symbol, "side": exit_side, "qty": qty,
                                               "status": "placed", "order_id": order.get("id") if order else "", "note": "exit"})
                    # Log fill simple
                    self.log_fills.write_row({"ts": ts, "symbol": symbol, "side": exit_side, "price": c, "qty": qty,
                                              "order_id": order.get("id") if order else ""})
                    ctx.fsm.on_close()

            if PRINT_OHLCV_SAMPLE and (ctx.ticks % 20 == 0) and not QUIET:
                print(f"[{symbol}] last close={c} (ticks={ctx.ticks})", flush=True)

            await asyncio.sleep(0.1 if QUIET else 0.01)

    # -------------------------------------------------------------------------
    # Run
    # -------------------------------------------------------------------------
    async def run(self):
        # Notifier / CommandStream si non fournis
        if not self.notifier or not self.command_stream:
            self.notifier, self.command_stream = await build_notifier_and_stream()

        # Signaux OS pour arrêt propre
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(f"os:{s.name}")))
            except NotImplementedError:
                # Windows / environnements limités
                pass

        # Boot watchlist
        await self._task_watchlist_boot()

        # Tâches
        tasks = []

        # Heartbeat + stats (respectent QUIET dans services.utils)
        tasks.append(asyncio.create_task(heartbeat_task(self.get_running, period=15.0)))
        tasks.append(asyncio.create_task(log_stats_task(self.get_running, lambda: self._ticks_total,
                                                        lambda: list(self.symbol_contexts.keys()), period=30.0)))

        # Watchlist refresh
        tasks.append(asyncio.create_task(self._task_watchlist_refresh()))

        # Positions sync
        tasks.append(asyncio.create_task(self._task_positions_sync()))

        # Commandes
        tasks.append(asyncio.create_task(self._task_commands()))

        # Boucles trade par symbole
        for s in list(self.symbol_contexts.keys()):
            tasks.append(asyncio.create_task(self._task_trade_loop(s)))

        if self.notifier:
            await self.notifier.send("🟢 Orchestrator running (mode PRELAUNCH). Utilise /setup pour valider avant trading.")

        # Attente des tâches
        try:
            await asyncio.gather(*tasks)
        finally:
            if self.notifier:
                try:
                    await self.notifier.send("🔴 Orchestrator stopped.")
                except Exception:
                    pass

# -----------------------------------------------------------------------------
# Helper d’entrée unique (facultatif) — appelé par bot.py
# -----------------------------------------------------------------------------

async def run_orchestrator(exchange, config: Dict[str, Any], symbols: Optional[List[str]] = None,
                           notifier: Optional[Notifier] = None, command_stream: Optional[CommandStream] = None):
    orch = Orchestrator(exchange=exchange, config=config, symbols=symbols,
                        notifier=notifier, command_stream=command_stream)
    await orch.run()