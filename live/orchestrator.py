from __future__ import annotations

import asyncio, signal, time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService, OrderRequest
from scalp.strategy import generate_signal, Signal

# modules internes séparés
from live.watchlist import WatchlistManager
from live.ohlcv_service import OhlcvService
from live.journal import LogWriter

# Optionnels
try:
    from live.telegram_async import TelegramAsync
except Exception:
    TelegramAsync = None  # type: ignore

from live.position_fsm import (
    PositionFSM, STATE_FLAT, STATE_OPEN, STATE_PENDING_EXIT, STATE_PENDING_ENTRY
)

@dataclass
class SymbolContext:
    symbol: str
    ohlcv: List[Dict[str, float]]
    position_open: bool = False
    last_signal_ts: float = 0.0

class Orchestrator:
    def __init__(self, exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
        self.exchange = exchange
        self.order_service = order_service
        self.config = config

        self.symbols = [s.replace("_","").upper() for s in symbols] or ["BTCUSDT","ETHUSDT"]
        self.ctx: Dict[str, SymbolContext] = {s: SymbolContext(s, []) for s in self.symbols}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._paused = False
        self._heartbeat_ts = 0.0

        # Services
        self.ohlcv = OhlcvService(self.exchange)
        self.logs = LogWriter(dirpath=__import__("os").path.join(__import__("os").path.dirname(__file__), "logs"))
        self.logs.init("signals.csv",   ["ts","symbol","side","entry","sl","tp1","tp2","last"])
        self.logs.init("orders.csv",    ["ts","symbol","side","price","sl","tp","risk_pct","status","order_id"])
        self.logs.init("fills.csv",     ["ts","symbol","order_id","trade_id","price","qty","fee"])
        self.logs.init("positions.csv", ["ts","symbol","state","qty","entry"])

        # Telegram
        if TelegramAsync is not None:
            self._tg = TelegramAsync(token=getattr(config,"TELEGRAM_BOT_TOKEN",None),
                                     chat_id=getattr(config,"TELEGRAM_CHAT_ID",None))
        else:
            self._tg = None

        # FSM + Watchlist
        self._fsm = PositionFSM(self.symbols)
        self._watch = WatchlistManager(
            exchange=self.exchange, only_suffix="USDT", top_n=10, period_s=120.0,
            on_update=self._apply_symbols_update,
            safe_call=lambda f, label: self._safe(f, label=label),
        )

    # ---------- utils ----------
    async def _sleep(self, s: float): 
        try: await asyncio.sleep(s)
        except asyncio.CancelledError: pass

    async def _safe(self, factory, *, label: str, backoff: float = 1.0, backoff_max: float = 30.0):
        delay = backoff
        while self._running:
            try:
                res = factory()
                if asyncio.iscoroutine(res): return await res
                return res
            except asyncio.CancelledError: raise
            except Exception as e:
                print(f"[orchestrator] {label} failed: {e!r}, retry in {delay:.1f}s")
                await self._sleep(delay); delay = min(backoff_max, delay*1.7)

    def _apply_symbols_update(self, new_syms: Sequence[str]) -> None:
        ns = [s.replace("_","").upper() for s in new_syms]
        if not ns or ns == self.symbols: return
        self.symbols = list(ns)
        for s in self.symbols:
            if s not in self.ctx: self.ctx[s] = SymbolContext(s, [])
            self._fsm.ensure_symbol(s)
        for s in list(self.ctx.keys()):
            if s not in self.symbols: del self.ctx[s]
        print(f"[watchlist] updated TOP10: {','.join(self.symbols)}")

    # ---------- tasks ----------
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
                fills_by_sym: Dict[str,List[Dict[str,Any]]] = {}
                for s, st in self._fsm.all().items():
                    if st.state in (STATE_PENDING_ENTRY, STATE_OPEN):
                        try:
                            fills = await self._safe(lambda s=s: self.exchange.get_fills(s, st.order_id, 50), label=f"get_fills:{s}")
                            fl = fills.get("data") if isinstance(fills, dict) else []
                            fills_by_sym[s] = fl
                            for f in fl:
                                self.logs.row("fills.csv", {
                                    "ts": int(time.time()*1000), "symbol": s,
                                    "order_id": f.get("orderId",""), "trade_id": f.get("tradeId",""),
                                    "price": float(f.get("price",0.0)), "qty": float(f.get("qty",0.0)),
                                    "fee": float(f.get("fee",0.0)),
                                })
                        except Exception: pass
                self._fsm.reconcile(pos_list, fills_by_sym)
                now = int(time.time()*1000)
                for s, st in self._fsm.all().items():
                    if s in self.ctx: self.ctx[s].position_open = (st.state in (STATE_OPEN, STATE_PENDING_EXIT))
                    self.logs.row("positions.csv", {"ts": now, "symbol": s, "state": st.state, "qty": st.qty, "entry": st.entry})
            except Exception as e:
                print(f"[positions] sync error: {e!r}")
            await self._sleep(5.0)

    async def _task_trade_loop(self, symbol: str):
        ctx = self.ctx[symbol]
        print(f"[trade-loop] start {symbol}")

        boot = await self._safe(lambda: self.ohlcv.fetch_once(symbol, "1m", 200), label=f"ohlcv_boot:{symbol}")
        ctx.ohlcv = self.ohlcv.normalize_rows(boot or [])
        if ctx.ohlcv: print(f"[debug:{symbol}] ohlcv sample -> dict={list(ctx.ohlcv[0].keys())}")

        while self._running:
            if self._paused: await self._sleep(1.0); continue

            tail = await self._safe(lambda: self.ohlcv.fetch_once(symbol, "1m", 2), label=f"ohlcv_tail:{symbol}")
            if tail: ctx.ohlcv = (self.ohlcv.normalize_rows(ctx.ohlcv)+self.ohlcv.normalize_rows(tail))[-400:]

            sig: Optional[Signal] = None
            try:
                rd = ctx.ohlcv
                ll = [[r["ts"],r["open"],r["high"],r["low"],r["close"],r["volume"]] for r in rd]
                cols = {"ts":[r["ts"] for r in rd], "open":[r["open"] for r in rd], "high":[r["high"] for r in rd],
                        "low":[r["low"] for r in rd], "close":[r["close"] for r in rd], "volume":[r["volume"] for r in rd]}
                try: sig = generate_signal(ohlcv=rd, config=self.config)
                except Exception:
                    try: sig = generate_signal(ohlcv=ll, config=self.config)
                    except Exception: sig = generate_signal(ohlcv=cols, config=self.config)
            except Exception as e:
                print(f"[trade-loop:{symbol}] signal error: {e!r}")

            if sig:
                last_close = ctx.ohlcv[-1]["close"] if ctx.ohlcv else float("nan")
                self.logs.row("signals.csv", {
                    "ts": int(time.time()*1000), "symbol": symbol,
                    "side": "LONG" if sig.side>0 else "SHORT",
                    "entry": float(getattr(sig,"entry", last_close) or last_close),
                    "sl": float(getattr(sig,"sl",0) or 0), "tp1": float(getattr(sig,"tp1",0) or 0),
                    "tp2": float(getattr(sig,"tp2",0) or 0), "last": float(last_close),
                })

            st = self._fsm.get(symbol)
            if sig and st.state == STATE_FLAT:
                try:
                    assets = await self._safe(lambda: self.exchange.get_assets(), label="get_assets")
                    equity_usdt = 0.0
                    if isinstance(assets, dict):
                        for a in (assets.get("data") or []):
                            if a.get("currency") == "USDT": equity_usdt = float(a.get("equity",0)); break

                    risk_pct = float(getattr(self.config,"RISK_PCT",0.01) or 0.01)
                    min_notional = float(getattr(self.config,"MIN_TRADE_USDT",5) or 5)
                    if equity_usdt * risk_pct < min_notional: await self._sleep(1.0); continue
                    if time.time() - ctx.last_signal_ts < 5.0: continue

                    entry_price = float(getattr(sig,"entry", ctx.ohlcv[-1]["close"]))
                    req = OrderRequest(
                        symbol=symbol, side=("long" if sig.side>0 else "short"),
                        price=entry_price, sl=float(getattr(sig,"sl",0) or 0) or None,
                        tp=float(getattr(sig,"tp1",0) or 0) or None, risk_pct=risk_pct,
                    )
                    res = self.order_service.prepare_and_place(equity_usdt, req)
                    if res.accepted:
                        ctx.last_signal_ts = time.time()
                        self.logs.row("orders.csv", {
                            "ts": int(time.time()*1000), "symbol": symbol, "side": req.side,
                            "price": req.price, "sl": req.sl or 0.0, "tp": req.tp or 0.0,
                            "risk_pct": req.risk_pct, "status": res.status or "accepted", "order_id": getattr(res,"order_id",""),
                        })
                        self._fsm.set_pending_entry(symbol, getattr(res,"order_id",""), req.side)
                        if self._tg and self._tg.enabled():
                            await self._tg.send_message(f"Order accepted: {symbol} {req.side} @ {req.price}")
                except Exception as e:
                    print(f"[trade-loop:{symbol}] order error: {e!r}")

            await self._sleep(1.0)

    # ---------- lifecycle ----------
    async def run(self):
        if self._running: return
        self._running = True

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try: loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(reason=f"signal:{s.name}")))
            except NotImplementedError: pass

        # TOP10 au boot
        try:
            top = await self._watch.boot_topN()
            if top: self._apply_symbols_update(top)
        except Exception as e:
            print(f"[watchlist] boot error: {e!r}")

        self._tasks = [
            asyncio.create_task(self._task_heartbeat(), name="heartbeat"),
            asyncio.create_task(self._watch.task_auto_refresh(), name="watchlist"),
            asyncio.create_task(self._task_positions_sync(), name="positions"),
            *[asyncio.create_task(self._task_trade_loop(s), name=f"trade:{s}") for s in self.symbols],
        ]
        if self._tg and self._tg.enabled():
            self._tasks.append(asyncio.create_task(self._task_telegram(), name="telegram"))  # type: ignore

        print("[orchestrator] running")
        try: await asyncio.gather(*self._tasks)
        except asyncio.CancelledError: pass
        finally: print("[orchestrator] stopped")

    async def _task_telegram(self):  # simple handler
        await self._tg.send_message("Orchestrator started ✅")
        while self._running:
            try:
                updates = await self._tg.poll_commands(timeout_s=20)  # type: ignore
                for u in updates:
                    txt = (u.get("text") or "").lower().strip()
                    if txt.startswith("/status"):
                        alive = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._heartbeat_ts)) if self._heartbeat_ts else "n/a"
                        await self._tg.send_message(f"running:{self._running} paused:{self._paused}\nheartbeat:{alive}\nsymbols:{','.join(self.symbols)}")  # type: ignore
                    elif txt.startswith("/pause"):  self._paused=True;  await self._tg.send_message("Paused ✅")  # type: ignore
                    elif txt.startswith("/resume"): self._paused=False; await self._tg.send_message("Resumed ▶️") # type: ignore
                    elif txt.startswith("/close"):  await self.stop("telegram:/close")
            except asyncio.CancelledError: break
            except Exception: await self._sleep(2.0)

    async def stop(self, reason: str = "unknown"):
        if not self._running: return
        print(f"[orchestrator] stopping: {reason}")
        self._running = False
        for t in self._tasks:
            try: t.cancel()
            except Exception: pass
        await asyncio.sleep(0)

async def run_orchestrator(exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
    orch = Orchestrator(exchange, order_service, config, symbols)
    await orch.run()