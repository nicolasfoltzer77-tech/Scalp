# live/orchestrator.py
from __future__ import annotations

import asyncio
import signal
import time
import os
import csv
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from scalp.adapters.bitget import BitgetFuturesClient
try:
    from live.telegram_async import TelegramAsync
except Exception:
    TelegramAsync = None  # type: ignore
try:
    from scalp.adapters.market_data import MarketData
except Exception:
    MarketData = None  # type: ignore

from scalp.services.order_service import OrderService, OrderRequest
from scalp.strategy import generate_signal, Signal

# FSM positions
from live.position_fsm import (
    PositionFSM, STATE_FLAT, STATE_OPEN, STATE_PENDING_ENTRY, STATE_PENDING_EXIT
)

# -------------------- Types simples --------------------
@dataclass
class SymbolContext:
    symbol: str
    ohlcv: List[Dict[str, float]]
    position_open: bool = False
    last_signal_ts: float = 0.0


# =======================================================
#                 ORCHESTRATEUR ASYNC
# =======================================================
class Orchestrator:
    def __init__(self, exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
        self.exchange = exchange
        self.order_service = order_service
        self.config = config
        self.symbols = [s.replace("_", "").upper() for s in symbols]
        self.ctx: Dict[str, SymbolContext] = {s: SymbolContext(s, []) for s in self.symbols}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._heartbeat_ts = 0.0
        self._paused = False

        # journaux — dossier forcé à côté de ce fichier
        self._log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(self._log_dir, exist_ok=True)
        self._init_log_file("signals.csv", ["ts", "symbol", "side", "entry", "sl", "tp1", "tp2", "last"])
        self._init_log_file("orders.csv", ["ts", "symbol", "side", "price", "sl", "tp", "risk_pct", "status", "order_id"])
        self._init_log_file("fills.csv", ["ts", "symbol", "order_id", "trade_id", "price", "qty", "fee"])
        self._init_log_file("positions.csv", ["ts", "symbol", "state", "qty", "entry"])

        # Telegram (facultatif)
        if TelegramAsync is not None:
            token = getattr(self.config, "TELEGRAM_BOT_TOKEN", None)
            chat = getattr(self.config, "TELEGRAM_CHAT_ID", None)
            self._tg = TelegramAsync(token=token, chat_id=chat)
        else:
            self._tg = None

        self._md = MarketData(self.exchange) if MarketData is not None else None

        # FSM positions
        self._fsm = PositionFSM(self.symbols)

    # ----------------- utilitaires communs -----------------
    async def _sleep(self, secs: float) -> None:
        try:
            await asyncio.sleep(secs)
        except asyncio.CancelledError:
            pass

    async def _safe(self, coro_factory, *, label: str, backoff: float = 1.0, backoff_max: float = 30.0):
        delay = backoff
        while self._running:
            try:
                return await coro_factory()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[orchestrator] {label} failed: {e!r}, retry in {delay:.1f}s")
                await self._sleep(delay)
                delay = min(backoff_max, delay * 1.7)

    # ----------------- journalisation simple -----------------
    def _init_log_file(self, fname: str, headers: List[str]) -> None:
        fpath = os.path.join(self._log_dir, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=headers).writeheader()

    def _log_row(self, fname: str, row: Dict[str, Any]) -> None:
        fpath = os.path.join(self._log_dir, fname)
        with open(fpath, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=list(row.keys())).writerow(row)

    # ----------------- Normalisation OHLCV -----------------
    def _normalize_rows(self, rows: Any) -> List[Dict[str, float]]:
        out: List[Dict[str, float]] = []
        if not rows:
            return out
        for r in rows:
            if isinstance(r, dict):
                ts = int(r.get("ts") or r.get("time") or r.get("timestamp") or 0)
                o = float(r.get("open", 0.0)); h = float(r.get("high", o)); l = float(r.get("low", o))
                c = float(r.get("close", o)); v = float(r.get("volume", r.get("vol", 0.0)))
            else:
                rr = list(r)
                if len(rr) >= 6 and isinstance(rr[0], (int, float)) and rr[0] > 10**10:
                    ts, o, h, l, c = int(rr[0]), float(rr[1]), float(rr[2]), float(rr[3]), float(rr[4]); v = float(rr[5])
                else:
                    o = float(rr[0]) if len(rr) > 0 else 0.0
                    h = float(rr[1]) if len(rr) > 1 else o
                    l = float(rr[2]) if len(rr) > 2 else o
                    c = float(rr[3]) if len(rr) > 3 else o
                    v = float(rr[4]) if len(rr) > 4 else 0.0
                    ts = int(rr[5]) if len(rr) > 5 else 0
            out.append({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
        return out

    def _coerce_for_strategy(self, rows_any: Any):
        rd = self._normalize_rows(rows_any or [])
        rl = [[r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]] for r in rd]
        cols = {"ts": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
        for r in rd:
            cols["ts"].append(r["ts"]); cols["open"].append(r["open"]); cols["high"].append(r["high"])
            cols["low"].append(r["low"]); cols["close"].append(r["close"]); cols["volume"].append(r["volume"])
        return rd, rl, cols

    # ------------- Lecture OHLCV normalisée -------------
    async def _fetch_ohlcv_once(self, symbol: str, limit: int = 100) -> List[Dict[str, float]]:
        if self._md is not None:
            try:
                d = await self._safe(lambda: asyncio.to_thread(self._md.get_ohlcv, symbol, "1m", limit),
                                     label=f"md.get_ohlcv:{symbol}")
                if isinstance(d, dict) and d.get("success") and d.get("data"):
                    return self._normalize_rows(d["data"])
            except Exception:
                pass
        rows: List[Any] = []
        try:
            data = await self._safe(lambda: asyncio.to_thread(self.exchange.get_kline, symbol, interval="1m"),
                                    label=f"get_kline:{symbol}")
        except Exception:
            data = None
        if isinstance(data, dict):
            rows = data.get("data") or data.get("result") or data.get("records") or data.get("list") or data.get("items") or data.get("candles") or []
            guard = 0
            while isinstance(rows, dict) and guard < 3:
                rows = rows.get("data") or rows.get("result") or rows.get("records") or rows.get("list") or rows.get("items") or rows.get("candles") or rows.get("klines") or rows.get("bars") or []
                guard += 1
        elif isinstance(data, (list, tuple)):
            rows = list(data)
        out = self._normalize_rows(rows)[-limit:]
        if out:
            return out
        try:
            tkr = await self._safe(lambda: asyncio.to_thread(self.exchange.get_ticker, symbol),
                                   label=f"get_ticker:{symbol}")
            items: List[Any] = []
            if isinstance(tkr, dict):
                items = tkr.get("data") or tkr.get("result") or tkr.get("tickers") or []
            elif isinstance(tkr, (list, tuple)):
                items = list(tkr)
            if items:
                last = items[0]
                if isinstance(last, dict):
                    p = float(last.get("lastPrice", last.get("close", last.get("markPrice", 0.0))))
                    v = float(last.get("volume", last.get("usdtVolume", last.get("quoteVolume", 0.0))))
                else:
                    seq = list(last)
                    if len(seq) >= 5:
                        first = isinstance(seq[0], (int, float)) and seq[0] > 10**10
                        if first: p = float(seq[4]); v = float(seq[5]) if len(seq) > 5 else 0.0
                        else:     p = float(seq[3] if len(seq) > 3 else seq[-2]); v = float(seq[4] if len(seq) > 4 else seq[-1])
                    else:
                        p, v = float(seq[-1]) if seq else 0.0, 0.0
                ts = int(time.time()*1000)
                return [{"ts": ts, "open": p, "high": p, "low": p, "close": p, "volume": v}]
        except Exception:
            pass
        return []

    # ----------------- Watchlist: TOP 10 -----------------
    async def _task_refresh_watchlist(self):
        while self._running:
            try:
                all_tk = await self._safe(lambda: asyncio.to_thread(self.exchange.get_ticker, None),
                                          label="get_tickers")
                items = []
                if isinstance(all_tk, dict):
                    items = all_tk.get("data") or all_tk.get("result") or all_tk.get("tickers") or []
                elif isinstance(all_tk, (list, tuple)):
                    items = list(all_tk)
                norm = []
                for t in items:
                    if isinstance(t, dict):
                        s = (t.get("symbol") or t.get("instId") or "").replace("_", "").upper()
                        v = float(t.get("volume", t.get("usdtVolume", t.get("quoteVolume", 0.0))) or 0.0)
                        if s.endswith("USDT"): norm.append((s, v))
                norm.sort(key=lambda x: x[1], reverse=True)
                top = [s for s, _ in norm[:10]]
                if top and top != self.symbols:
                    self.symbols = top
                    for s in top:
                        if s not in self.ctx: self.ctx[s] = SymbolContext(s, [])
                        self._fsm.ensure_symbol(s)
                    for s in list(self.ctx.keys()):
                        if s not in top: del self.ctx[s]
                    print(f"[watchlist] updated TOP10: {','.join(self.symbols)}")
            except Exception as e:
                print(f"[watchlist] error: {e!r}")
            await self._sleep(120.0)

    # ----------------- Heartbeat -----------------
    async def _task_heartbeat(self):
        while self._running:
            self._heartbeat_ts = time.time()
            print("[heartbeat] alive")
            await self._sleep(15)

    def _status_text(self) -> str:
        alive = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._heartbeat_ts)) if self._heartbeat_ts else "n/a"
        syms = ",".join(self.symbols) or "-"
        return (f"Scalp bot\nrunning: {self._running}\npaused: {self._paused}\n"
                f"heartbeat: {alive}\nsymbols: {syms}")

    # ----------------- Positions Sync -----------------
    async def _task_positions_sync(self):
        """
        Tâche de réconciliation: positions Bitget + fills par symbole.
        Met à jour la FSM + ctx.position_open et journalise.
        """
        while self._running:
            try:
                # 1) positions ouvertes
                pos = await self._safe(lambda: asyncio.to_thread(self.exchange.get_open_positions, None),
                                       label="get_open_positions")
                pos_list = pos.get("data") if isinstance(pos, dict) else []
                # 2) fills pour symboles en attente d'entrée
                fills_by_sym: Dict[str, List[Dict[str, Any]]] = {}
                for s, st in self._fsm.all().items():
                    if st.state == STATE_PENDING_ENTRY or st.state == STATE_OPEN:
                        try:
                            fills = await self._safe(lambda s=s: asyncio.to_thread(self.exchange.get_fills, s, st.order_id, 50),
                                                     label=f"get_fills:{s}")
                            fills_list = fills.get("data") if isinstance(fills, dict) else []
                            fills_by_sym[s] = fills_list
                            # log
                            for f in fills_list:
                                self._log_row("fills.csv", {
                                    "ts": int(time.time()*1000),
                                    "symbol": s,
                                    "order_id": f.get("orderId", ""),
                                    "trade_id": f.get("tradeId", ""),
                                    "price": float(f.get("price", 0.0)),
                                    "qty": float(f.get("qty", 0.0)),
                                    "fee": float(f.get("fee", 0.0)),
                                })
                        except Exception:
                            pass

                # 3) reconcile FSM
                self._fsm.reconcile(pos_list, fills_by_sym)

                # 4) reporter dans ctx + log snapshot positions
                now = int(time.time()*1000)
                for s, st in self._fsm.all().items():
                    if s in self.ctx:
                        self.ctx[s].position_open = (st.state == STATE_OPEN or st.state == STATE_PENDING_EXIT)
                    self._log_row("positions.csv", {
                        "ts": now, "symbol": s, "state": st.state, "qty": st.qty, "entry": st.entry
                    })

            except Exception as e:
                print(f"[positions] sync error: {e!r}")
            await self._sleep(5.0)

    # ----------------- Telegram -----------------
    async def _task_telegram(self):
        if not self._tg or not self._tg.enabled():
            while self._running:
                await self._sleep(2.0)
            return
        await self._tg.send_message("Orchestrator started ✅")
        await self._tg.send_message(self._status_text())
        while self._running:
            try:
                updates = await self._tg.poll_commands(timeout_s=20)
                for u in updates:
                    text = (u.get("text") or "").strip()
                    low = text.lower()
                    if low.startswith("/status"):
                        await self._tg.send_message(self._status_text())
                    elif low.startswith("/pause"):
                        self._paused = True
                        await self._tg.send_message("Paused ✅ (no new entries)")
                    elif low.startswith("/resume"):
                        self._paused = False
                        await self._tg.send_message("Resumed ▶️")
                    elif low.startswith("/flat_all"):
                        for s in self.symbols:
                            self._fsm.force_flat(s)
                        await self._tg.send_message("All states set to FLAT")
                    elif low.startswith("/flat"):
                        parts = text.split()
                        if len(parts) == 2:
                            s = parts[1].replace("_", "").upper()
                            self._fsm.force_flat(s)
                            await self._tg.send_message(f"{s} set to FLAT")
                        else:
                            await self._tg.send_message("Usage: /flat SYMBOL")
                    elif low.startswith("/symbols"):
                        parts = text.split(None, 1)
                        if len(parts) == 2:
                            syms = [s.strip().replace("_", "").upper() for s in parts[1].split(",") if s.strip()]
                            if syms:
                                self.symbols = syms[:10]
                                for s in self.symbols:
                                    if s not in self.ctx: self.ctx[s] = SymbolContext(s, [])
                                    self._fsm.ensure_symbol(s)
                                await self._tg.send_message(f"Symbols updated: {','.join(self.symbols)}")
                            else:
                                await self._tg.send_message("Usage: /symbols BTCUSDT,ETHUSDT")
                        else:
                            await self._tg.send_message("Usage: /symbols BTCUSDT,ETHUSDT")
                    elif low.startswith("/close"):
                        await self._tg.send_message("Closing…")
                        await self.stop(reason="telegram:/close")
                    else:
                        await self._tg.send_message("Commands: /status, /pause, /resume, /flat SYMBOL, /flat_all, /symbols SYM1,SYM2, /close")
            except asyncio.CancelledError:
                break
            except Exception:
                await self._sleep(2.0)

    # ----------------- Trade loop -----------------
    async def _task_trade_loop(self, symbol: str):
        ctx = self.ctx[symbol]
        print(f"[trade-loop] start {symbol}")

        boot_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=200),
                                     label=f"fetch_ohlcv_boot:{symbol}")
        ctx.ohlcv = self._normalize_rows(boot_rows or [])
        if ctx.ohlcv:
            print(f"[debug:{symbol}] ohlcv sample -> dict={list(ctx.ohlcv[0].keys())}")

        while self._running:
            if self._paused:
                await self._sleep(1.0)
                continue

            new_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=2),
                                        label=f"fetch_ohlcv_tail:{symbol}")
            if new_rows:
                ctx.ohlcv = (self._normalize_rows(ctx.ohlcv) + self._normalize_rows(new_rows))[-400:]

            sig: Optional[Signal] = None
            try:
                rd, rl, cols = self._coerce_for_strategy(ctx.ohlcv)
                try:
                    sig = generate_signal(ohlcv=rd, config=self.config)
                except Exception as e1:
                    try:
                        sig = generate_signal(ohlcv=rl, config=self.config)
                    except Exception as e2:
                        try:
                            sig = generate_signal(ohlcv=cols, config=self.config)
                        except Exception as e3:
                            print(f"[trade-loop:{symbol}] generate_signal error: {e3!r} (fallback after {e1!r} / {e2!r})")
                            sig = None
            except Exception as e:
                print(f"[trade-loop:{symbol}] normalize error: {e!r}")
                sig = None

            if sig:
                try:
                    last_close = ctx.ohlcv[-1]["close"] if ctx.ohlcv else float("nan")
                    print(f"[signal:{symbol}] side={'LONG' if sig.side>0 else 'SHORT'} entry={sig.entry} sl={sig.sl} tp1={getattr(sig,'tp1',None)} tp2={getattr(sig,'tp2',None)} last={last_close}")
                    self._log_row("signals.csv", {
                        "ts": int(time.time()*1000), "symbol": symbol,
                        "side": "LONG" if sig.side>0 else "SHORT",
                        "entry": float(sig.entry), "sl": float(sig.sl),
                        "tp1": float(getattr(sig, "tp1", 0) or 0), "tp2": float(getattr(sig, "tp2", 0) or 0),
                        "last": float(last_close),
                    })
                except Exception:
                    pass

            # Exécuter si signal et pas de position ouverte (côté FSM)
            st = self._fsm.get(symbol)
            if sig and st.state in (STATE_FLAT,):
                try:
                    assets = await self._safe(lambda: asyncio.to_thread(self.exchange.get_assets), label="get_assets")
                    equity_usdt = 0.0
                    if isinstance(assets, dict):
                        for a in (assets.get("data") or []):
                            if a.get("currency") == "USDT":
                                equity_usdt = float(a.get("equity", 0)); break

                    risk_pct = float(getattr(self.config, "RISK_PCT", 0.01) or 0.01)
                    min_notional = float(getattr(self.config, "MIN_TRADE_USDT", 5) or 5)
                    if equity_usdt * risk_pct < min_notional:
                        print(f"[order:{symbol}] skipped: notional too small (equity*risk={equity_usdt*risk_pct:.2f} < {min_notional})")
                        await self._sleep(1.0); continue
                    if time.time() - ctx.last_signal_ts < 5.0:
                        continue

                    req = OrderRequest(
                        symbol=sig.symbol or symbol,
                        side="long" if sig.side > 0 else "short",
                        price=float(sig.entry),
                        sl=float(sig.sl),
                        tp=float(sig.tp1) if getattr(sig, "tp1", None) else (float(sig.tp2) if getattr(sig, "tp2", None) else None),
                        risk_pct=risk_pct,
                    )
                    res = self.order_service.prepare_and_place(equity_usdt, req)
                    if res.accepted:
                        ctx.last_signal_ts = time.time()
                        print(f"[order] {symbol} accepted")
                        self._log_row("orders.csv", {
                            "ts": int(time.time()*1000), "symbol": symbol, "side": req.side,
                            "price": req.price, "sl": req.sl or 0.0, "tp": req.tp or 0.0,
                            "risk_pct": req.risk_pct, "status": res.status or "accepted", "order_id": res.order_id or "",
                        })
                        order_id = (res.order_id or "") if hasattr(res, "order_id") else ""
                        self._fsm.set_pending_entry(symbol, order_id, req.side)
                        if self._tg and self._tg.enabled():
                            await self._tg.send_message(f"Order accepted: {symbol} {req.side} @ {req.price}")
                    else:
                        print(f"[order] {symbol} rejected: {res.reason}")
                        if self._tg and self._tg.enabled():
                            await self._tg.send_message(f"Order rejected: {symbol} reason={res.reason}")
                except Exception as e:
                    print(f"[trade-loop:{symbol}] order error: {e!r}")

            await self._sleep(1.0)

    # ----------------- Cycle de vie -----------------
    async def run(self):
        if self._running: return
        self._running = True
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(reason=f"signal:{s.name}")))
            except NotImplementedError:
                pass

        self._tasks = [
            asyncio.create_task(self._task_heartbeat(), name="heartbeat"),
            asyncio.create_task(self._task_refresh_watchlist(), name="watchlist"),
            asyncio.create_task(self._task_positions_sync(), name="positions"),
            *(
                asyncio.create_task(self._task_trade_loop(s), name=f"trade:{s}")
                for s in self.symbols
            ),
        ]
        if self._tg and self._tg.enabled():
            self._tasks.append(asyncio.create_task(self._task_telegram(), name="telegram"))

        print("[orchestrator] running")
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            print("[orchestrator] stopped")

    async def stop(self, reason: str = "unknown"):
        if not self._running: return
        print(f"[orchestrator] stopping: {reason}")
        self._running = False
        for t in self._tasks:
            try: t.cancel()
            except Exception: pass
        await asyncio.sleep(0)


# Helper
async def run_orchestrator(exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
    orch = Orchestrator(exchange, order_service, config, symbols)
    await orch.run()