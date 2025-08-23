# scalp/live/orchestrator.py
from __future__ import annotations

import asyncio
import os
import signal
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

# Adapters / services cœur
from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService

# Stratégie
from scalp.strategy import generate_signal, Signal  # noqa: F401

# Modules internes factorisés
from live.watchlist import WatchlistManager
from live.ohlcv_service import OhlcvService
from live.journal import LogWriter
from live.orders import OrderExecutor
from live.state_store import StateStore

# FSM positions
from live.position_fsm import (
    PositionFSM,
    STATE_FLAT,
    STATE_OPEN,
    STATE_PENDING_ENTRY,
    STATE_PENDING_EXIT,
)

# Notification/Commandes découplées (nouveau)
from live.notify import Notifier, NullNotifier, TelegramNotifier, CommandStream


# =========================  Types simples  =========================
@dataclass
class SymbolContext:
    symbol: str
    ohlcv: List[Dict[str, float]]
    position_open: bool = False
    last_signal_ts: float = 0.0


# =========================  ORCHESTRATEUR  =========================
class Orchestrator:
    """
    Orchestrateur asyncio MINCE :
      - Watchlist TOP10 USDT (boot + refresh)
      - Service OHLCV (normalisation/fallback)
      - Journal CSV (signals, orders, fills, positions, watchlist)
      - Exécution d’ordres via OrderExecutor (sizing + OrderService)
      - FSM positions + persistance JSON (reprise après crash)
      - Notifications / commandes **découplées** via Notifier & CommandStream
    """

    def __init__(
        self,
        exchange: BitgetFuturesClient,
        order_service: OrderService,
        config: Any,
        symbols: Sequence[str],
    ) -> None:
        self.exchange = exchange
        self.config = config

        # Liste initiale (remplacée par watchlist au boot)
        self.symbols = [s.replace("_", "").upper() for s in symbols] or ["BTCUSDT", "ETHUSDT"]
        self.ctx: Dict[str, SymbolContext] = {s: SymbolContext(s, []) for s in self.symbols}

        self._running = False
        self._paused = False
        self._tasks: List[asyncio.Task] = []
        self._heartbeat_ts = 0.0

        # ---- Services factorisés
        self.ohlcv = OhlcvService(self.exchange)

        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        self.logs = LogWriter(log_dir)
        self.logs.init("signals.csv",   ["ts", "symbol", "side", "entry", "sl", "tp1", "tp2", "last"])
        self.logs.init("orders.csv",    ["ts", "symbol", "side", "price", "sl", "tp", "risk_pct", "status", "order_id"])
        self.logs.init("fills.csv",     ["ts", "symbol", "order_id", "trade_id", "price", "qty", "fee"])
        self.logs.init("positions.csv", ["ts", "symbol", "state", "qty", "entry"])
        self.logs.init("watchlist.csv", ["ts", "symbols"])

        self.orders = OrderExecutor(order_service=order_service, exchange=self.exchange, config=self.config)

        # FSM + persistance
        self._fsm = PositionFSM(self.symbols)
        self.state = StateStore(os.path.join(log_dir, "state.json"), period_s=10.0)

        # Watchlist (TOP10 USDT)
        self._watch = WatchlistManager(
            exchange=self.exchange,
            only_suffix="USDT",
            top_n=10,
            period_s=120.0,
            on_update=self._apply_symbols_update,
            safe_call=lambda f, label: self._safe(f, label=label),
        )

        # DEBUG: écrire des lignes "NONE" dans signals.csv si aucun signal (pour valider le pipeline)
        self._debug_noop = str(os.getenv("DEBUG_LOG_NOOP", "0")) == "1"
        self._last_noop_ts = 0.0

        # ---- Notifications / Commandes (découplées)
        token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
        chat  = getattr(config, "TELEGRAM_CHAT_ID", None)
        self.notifier: Notifier = TelegramNotifier(token, chat) if (token and chat) else NullNotifier()
        self._cmd_stream: Optional[CommandStream] = CommandStream(token, chat) if (token and chat) else None

        # Tentative de restauration d’état
        snap = self.state.load_state()
        for sym, ts in (snap.get("last_signal_ts") or {}).items():
            if sym in self.ctx:
                try:
                    self.ctx[sym].last_signal_ts = float(ts)
                except Exception:
                    pass
        for sym, st in (snap.get("fsm") or {}).items():
            try:
                itm = self._fsm.get(sym)
                itm.state = st.get("state", itm.state)
                itm.side = st.get("side", itm.side)
                itm.qty = float(st.get("qty", itm.qty))
                itm.entry = float(st.get("entry", itm.entry))
                itm.order_id = st.get("order_id", itm.order_id)
            except Exception:
                pass

    # --------------------- Utilitaires ---------------------
    async def _sleep(self, secs: float) -> None:
        try:
            await asyncio.sleep(secs)
        except asyncio.CancelledError:
            pass

    async def _safe(
        self,
        factory,
        *,
        label: str,
        backoff: float = 1.0,
        backoff_max: float = 30.0,
    ):
        """Retry exponentiel commun (sync/async)."""
        delay = backoff
        while self._running:
            try:
                res = factory()
                if asyncio.iscoroutine(res):
                    return await res
                return res
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[orchestrator] {label} failed: {e!r}, retry in {delay:.1f}s")
                await self._sleep(delay)
                delay = min(backoff_max, delay * 1.7)

    # ----------------- Watchlist update hook -----------------
    def _apply_symbols_update(self, new_syms: Sequence[str]) -> None:
        ns = [s.replace("_", "").upper() for s in new_syms]
        if not ns or ns == self.symbols:
            return
        self.symbols = list(ns)

        # Sync contexts & FSM
        for s in self.symbols:
            if s not in self.ctx:
                self.ctx[s] = SymbolContext(s, [])
            self._fsm.ensure_symbol(s)
        for s in list(self.ctx.keys()):
            if s not in self.symbols:
                del self.ctx[s]

        joined = ",".join(self.symbols)
        print(f"[watchlist] TOP{len(self.symbols)} = {joined}")
        self.logs.row("watchlist.csv", {"ts": int(time.time() * 1000), "symbols": joined})
        asyncio.create_task(self.notifier.send(f"🔝 Watchlist: {joined}"))

    # --------------------- Tasks principales ---------------------
    async def _task_heartbeat(self):
        while self._running:
            self._heartbeat_ts = time.time()
            print("[heartbeat] alive")
            await self._sleep(15)

    async def _task_positions_sync(self):
        while self._running:
            try:
                pos = await self._safe(lambda: self.exchange.get_open_positions(None), label="get_open_positions")
                pos_list = pos.get("data") if isinstance(pos, dict) else []

                fills_by_sym: Dict[str, List[Dict[str, Any]]] = {}
                for sym, st in self._fsm.all().items():
                    if st.state in (STATE_PENDING_ENTRY, STATE_OPEN):
                        fl = self.orders.fetch_fills(sym, st.order_id, 50)
                        fills_by_sym[sym] = fl
                        for f in fl:
                            self.logs.row(
                                "fills.csv",
                                {
                                    "ts": int(time.time() * 1000),
                                    "symbol": sym,
                                    "order_id": f.get("orderId", ""),
                                    "trade_id": f.get("tradeId", ""),
                                    "price": float(f.get("price", 0.0)),
                                    "qty": float(f.get("qty", 0.0)),
                                    "fee": float(f.get("fee", 0.0)),
                                },
                            )

                self._fsm.reconcile(pos_list, fills_by_sym)

                now = int(time.time() * 1000)
                for sym, st in self._fsm.all().items():
                    if sym in self.ctx:
                        self.ctx[sym].position_open = st.state in (STATE_OPEN, STATE_PENDING_EXIT)
                    self.logs.row(
                        "positions.csv",
                        {"ts": now, "symbol": sym, "state": st.state, "qty": st.qty, "entry": st.entry},
                    )
            except Exception as e:
                print(f"[positions] sync error: {e!r}")

            await self._sleep(5.0)

    async def _task_trade_loop(self, symbol: str):
        ctx = self.ctx[symbol]
        print(f"[trade-loop] start {symbol}")

        boot = await self._safe(lambda: self.ohlcv.fetch_once(symbol, "1m", 200), label=f"ohlcv_boot:{symbol}")
        ctx.ohlcv = self.ohlcv.normalize_rows(boot or [])
        if ctx.ohlcv:
            print(f"[debug:{symbol}] ohlcv sample -> dict={list(ctx.ohlcv[0].keys())}")

        while self._running:
            if self._paused:
                await self._sleep(1.0)
                continue

            tail = await self._safe(lambda: self.ohlcv.fetch_once(symbol, "1m", 2), label=f"ohlcv_tail:{symbol}")
            if tail:
                ctx.ohlcv = (self.ohlcv.normalize_rows(ctx.ohlcv) + self.ohlcv.normalize_rows(tail))[-400:]

            # --- Appel stratégie (3 formes tolérées)
            sig: Optional[Signal] = None
            try:
                rd = ctx.ohlcv
                seq = [[r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]] for r in rd]
                cols = {
                    "ts": [r["ts"] for r in rd],
                    "open": [r["open"] for r in rd],
                    "high": [r["high"] for r in rd],
                    "low": [r["low"] for r in rd],
                    "close": [r["close"] for r in rd],
                    "volume": [r["volume"] for r in rd],
                }
                try:
                    sig = generate_signal(ohlcv=rd, config=self.config)
                except Exception:
                    try:
                        sig = generate_signal(ohlcv=seq, config=self.config)
                    except Exception:
                        sig = generate_signal(ohlcv=cols, config=self.config)
            except Exception as e:
                print(f"[trade-loop:{symbol}] signal error: {e!r}")

            if sig:
                last_close = ctx.ohlcv[-1]["close"] if ctx.ohlcv else float("nan")
                self.logs.row(
                    "signals.csv",
                    {
                        "ts": int(time.time() * 1000),
                        "symbol": symbol,
                        "side": "LONG" if sig.side > 0 else "SHORT",
                        "entry": float(getattr(sig, "entry", last_close) or last_close),
                        "sl": float(getattr(sig, "sl", 0) or 0),
                        "tp1": float(getattr(sig, "tp1", 0) or 0),
                        "tp2": float(getattr(sig, "tp2", 0) or 0),
                        "last": float(last_close),
                    },
                )
                # info console + notifier
                side_str = "LONG" if sig.side > 0 else "SHORT"
                print(f"[signal] {symbol} -> {side_str} entry={last_close}")
                await self.notifier.send(f"📈 {symbol}: {side_str} @ {last_close}")

            # --- Debug: écrire un "no-op" si pas de signal pendant longtemps
            if not sig and self._debug_noop:
                now = time.time()
                if now - self._last_noop_ts > 20.0:
                    last_close = ctx.ohlcv[-1]["close"] if ctx.ohlcv else float("nan")
                    self.logs.row(
                        "signals.csv",
                        {
                            "ts": int(now * 1000),
                            "symbol": symbol,
                            "side": "NONE",
                            "entry": float(last_close),
                            "sl": 0.0,
                            "tp1": 0.0,
                            "tp2": 0.0,
                            "last": float(last_close),
                        },
                    )
                    self._last_noop_ts = now

            # --- Ouverture d’ordre (pilotée FSM)
            st = self._fsm.get(symbol)
            if sig and st.state == STATE_FLAT:
                try:
                    risk_pct = float(getattr(self.config, "RISK_PCT", 0.01) or 0.01)
                    min_notional = float(getattr(self.config, "MIN_TRADE_USDT", 5) or 5)

                    if self.orders.get_equity_usdt() * risk_pct < min_notional:
                        await self._sleep(1.0)
                        continue
                    if time.time() - ctx.last_signal_ts < 5.0:
                        continue

                    entry_price = float(getattr(sig, "entry", ctx.ohlcv[-1]["close"]))
                    res = self.orders.place_entry(
                        symbol=symbol,
                        side=("long" if sig.side > 0 else "short"),
                        price=entry_price,
                        sl=float(getattr(sig, "sl", 0) or 0) or None,
                        tp=float(getattr(sig, "tp1", 0) or 0) or None,
                        risk_pct=risk_pct,
                    )
                    if res.accepted:
                        ctx.last_signal_ts = time.time()
                        self.logs.row(
                            "orders.csv",
                            {
                                "ts": int(time.time() * 1000),
                                "symbol": symbol,
                                "side": "long" if sig.side > 0 else "short",
                                "price": entry_price,
                                "sl": float(getattr(sig, "sl", 0) or 0),
                                "tp": float(getattr(sig, "tp1", 0) or 0),
                                "risk_pct": risk_pct,
                                "status": res.status or "accepted",
                                "order_id": res.order_id or "",
                            },
                        )
                        self._fsm.set_pending_entry(symbol, res.order_id or "", "long" if sig.side > 0 else "short")
                        await self.notifier.send(f"✅ Order accepted: {symbol} {'long' if sig.side > 0 else 'short'} @ {entry_price}")
                except Exception as e:
                    print(f"[trade-loop:{symbol}] order error: {e!r}")

            await self._sleep(1.0)

    # --------------------- Commandes (remplace l'ancien _task_telegram) ---------------------
    async def _task_commands(self):
        await self.notifier.send("Orchestrator started ✅\nCommands: /status • /pause • /resume • /stop")
        assert self._cmd_stream is not None
        async for text in self._cmd_stream:
            t = (text or "").strip().lower()
            if t.startswith("/status"):
                alive = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._heartbeat_ts)) if self._heartbeat_ts else "n/a"
                await self.notifier.send(
                    f"running:{self._running} paused:{self._paused}\n"
                    f"heartbeat:{alive}\n"
                    f"symbols:{','.join(self.symbols)}"
                )
            elif t.startswith("/pause"):
                self._paused = True
                await self.notifier.send("Paused ✅")
            elif t.startswith("/resume"):
                self._paused = False
                await self.notifier.send("Resumed ▶️")
            elif t.startswith("/stop"):
                await self.notifier.send("🛑 Stop demandé. Arrêt en cours…")
                await self.stop("telegram:/stop")
                break

    # --------------------- Snapshot état (autosave) ---------------------
    def _snapshot_state(self) -> dict:
        return {
            "last_signal_ts": {s: ctx.last_signal_ts for s, ctx in self.ctx.items()},
            "fsm": {
                s: {
                    "state": st.state,
                    "side": st.side,
                    "qty": st.qty,
                    "entry": st.entry,
                    "order_id": st.order_id,
                }
                for s, st in self._fsm.all().items()
            },
        }

    # --------------------- Cycle de vie ---------------------
    async def run(self):
        if self._running:
            return
        self._running = True

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(reason=f"signal:{s.name}")))
            except NotImplementedError:
                pass

        # TOPN immédiat au boot
        try:
            top = await self._watch.boot_topN()
            print(f"[watchlist] boot got: {top}")
            if top:
                self._apply_symbols_update(top)
        except Exception as e:
            print(f"[watchlist] boot error: {e!r}")

        # démarrage notifier
        await self.notifier.start()

        # Tasks
        self._tasks = [
            asyncio.create_task(self._task_heartbeat(), name="heartbeat"),
            asyncio.create_task(self._watch.task_auto_refresh(), name="watchlist"),
            asyncio.create_task(self._task_positions_sync(), name="positions"),
            asyncio.create_task(self.state.task_autosave(self._snapshot_state), name="state-save"),
            *[asyncio.create_task(self._task_trade_loop(s), name=f"trade:{s}") for s in self.symbols],
        ]
        if self._cmd_stream:
            self._tasks.append(asyncio.create_task(self._task_commands(), name="commands"))

        print("[orchestrator] running")
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            print("[orchestrator] stopped")

    async def stop(self, reason: str = "unknown"):
        if not self._running:
            return
        print(f"[orchestrator] stopping: {reason}")
        self._running = False
        for t in self._tasks:
            try:
                t.cancel()
            except Exception:
                pass
        # arrêt bus commandes + notifier
        try:
            if self._cmd_stream:
                await self._cmd_stream.stop()
            await self.notifier.stop()
        except Exception:
            pass
        await asyncio.sleep(0)


# Helper de lancement (appelé depuis bot.py)
async def run_orchestrator(
    exchange: BitgetFuturesClient,
    order_service: OrderService,
    config: Any,
    symbols: Sequence[str],
):
    orch = Orchestrator(exchange, order_service, config, symbols)
    await orch.run()