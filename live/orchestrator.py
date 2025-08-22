from __future__ import annotations
import asyncio
import signal
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scalp.adapters.bitget import BitgetFuturesClient
from scalp.adapters.market_data import MarketData
from scalp.services.order_service import OrderService, OrderRequest
from scalp.strategy import generate_signal, Signal
from live.telegram_async import TelegramAsync
from scalp.positions.state import PositionState, PositionStatus, PositionSide, Fill


@dataclass
class SymbolContext:
    symbol: str
    ohlcv: List[Dict]
    position_open: bool = False
    last_signal_ts: float = 0.0


class Orchestrator:
    """
    Orchestrateur asyncio: gère plusieurs tâches concurrentes.
    """

    def __init__(self, exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
        self.exchange = exchange
        self.order_service = order_service
        self.config = config
        self.symbols = list(symbols)
        self.ctx: Dict[str, SymbolContext] = {s: SymbolContext(s, []) for s in self.symbols}
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._heartbeat_ts = 0.0
        # util de normalisation utilisé partout
        self._row_keys = ("ts", "open", "high", "low", "close", "volume")
        # état positions par symbole
        self.pos: Dict[str, PositionState] = {s: PositionState(s, PositionSide.LONG) for s in self.symbols}
        self._paused = False
        self._tg = TelegramAsync(
            token=getattr(config, "TELEGRAM_BOT_TOKEN", None),
            chat_id=getattr(config, "TELEGRAM_CHAT_ID", None)
        )

    # ---------- normalisation OHLCV ----------
    def _normalize_rows(self, rows):
        """
        Garantit une liste de dicts {"ts","open","high","low","close","volume"}.
        Accepte: list[dict] OU list[list/tuple].
        """
        out = []
        if not rows:
            return out
        for r in rows:
            if isinstance(r, dict):
                d = {
                    "ts": int(r.get("ts") or r.get("time") or r.get("timestamp") or 0),
                    "open": float(r.get("open", 0.0)),
                    "high": float(r.get("high", r.get("open", 0.0))),
                    "low": float(r.get("low", r.get("open", 0.0))),
                    "close": float(r.get("close", r.get("open", 0.0))),
                    "volume": float(r.get("volume", r.get("vol", 0.0))),
                }
            else:
                rr = list(r)
                # tolérance longueurs partielles
                ts = int(rr[0]) if len(rr) > 0 and isinstance(rr[0], (int, float)) and rr[0] > 10**10 else 0
                if ts > 0:
                    o = float(rr[1]) if len(rr) > 1 else 0.0
                    h = float(rr[2]) if len(rr) > 2 else o
                    l = float(rr[3]) if len(rr) > 3 else o
                    c = float(rr[4]) if len(rr) > 4 else o
                    v = float(rr[5]) if len(rr) > 5 else 0.0
                else:
                    # format [o,h,l,c,v,(ts)]
                    o = float(rr[0]) if len(rr) > 0 else 0.0
                    h = float(rr[1]) if len(rr) > 1 else o
                    l = float(rr[2]) if len(rr) > 2 else o
                    c = float(rr[3]) if len(rr) > 3 else o
                    v = float(rr[4]) if len(rr) > 4 else 0.0
                    ts = int(rr[5]) if len(rr) > 5 else 0
                d = {"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v}
            out.append(d)
        return out

    # ---------- UTILITAIRES ----------
    async def _sleep(self, secs: float) -> None:
        try:
            await asyncio.sleep(secs)
        except asyncio.CancelledError:
            pass

    async def _safe(self, coro_factory, *, label: str, backoff: float = 1.0, backoff_max: float = 30.0):
        """
        Exécute de façon sûre **une fabrique de coroutine**.
        But: éviter « cannot reuse already awaited coroutine » en créant une nouvelle coroutine à chaque appel.
        """
        delay = backoff
        while self._running:
            try:
                coro = coro_factory()
                return await coro
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[orchestrator] {label} failed: {e!r}, retry in {delay:.1f}s")
                await self._sleep(delay)
                delay = min(backoff_max, delay * 1.7)

    def _status_text(self) -> str:
        alive = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._heartbeat_ts)) if self._heartbeat_ts else "n/a"
        syms = ",".join(self.symbols) or "-"
        return (
            f"Scalp bot\n"
            f"running: {self._running}\n"
            f"paused: {self._paused}\n"
            f"heartbeat: {alive}\n"
            f"symbols: {syms}"
        )

    # ---------- TACHES ----------
    async def _task_heartbeat(self):
        while self._running:
            self._heartbeat_ts = time.time()
            print("[heartbeat] alive")
            await self._sleep(15)

    async def _task_refresh_watchlist(self):
        # Placeholder: à relier à ta logique de sélection dynamique de paires
        while self._running:
            # Ici on pourrait filtrer par volume via exchange.get_ticker()
            await self._sleep(60)

    async def _fetch_ohlcv_once(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Récupère une petite fenêtre OHLCV via l’adaptateur MarketData (normalisé).
        """
        md = MarketData(self.exchange)
        data = md.get_ohlcv(symbol, interval="1m", limit=limit)
        return data.get("data", []) if isinstance(data, dict) else []

    async def _task_trade_loop(self, symbol: str):
        ctx = self.ctx[symbol]
        print(f"[trade-loop] start {symbol}")
        # Pré-chargement fenêtre
        boot_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=200),
                                     label=f"fetch_ohlcv_boot:{symbol}")
        ctx.ohlcv = self._normalize_rows(boot_rows or [])
        while self._running:
            if self._paused:
                await self._sleep(1.0)
                continue
            # 1) rafraîchir dernière bougie
            new_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=2),
                                        label=f"fetch_ohlcv_tail:{symbol}")
            if new_rows:
                # maintenir une fenêtre glissante
                ctx.ohlcv = (ctx.ohlcv + self._normalize_rows(new_rows))[-400:]
            # 2) générer signal
            try:
                # on envoie toujours une liste de dicts normalisés
                sig: Optional[Signal] = generate_signal(ohlcv=ctx.ohlcv, config=self.config)
            except Exception as e:
                print(f"[trade-loop:{symbol}] generate_signal error: {e!r}")
                sig = None
            # 3) exécuter
            if sig and not ctx.position_open:
                try:
                    assets = self.exchange.get_assets()
                    equity_usdt = 0.0
                    for a in (assets.get("data") or []):
                        if a.get("currency") == "USDT":
                            equity_usdt = float(a.get("equity", 0))
                            break
                    req = OrderRequest(
                        symbol=sig.symbol or symbol,
                        side="long" if sig.side > 0 else "short",
                        price=float(sig.entry),
                        sl=float(sig.sl),
                        tp=float(sig.tp1) if getattr(sig, "tp1", None) else (float(sig.tp2) if getattr(sig, "tp2", None) else None),
                        risk_pct=float(getattr(self.config, "RISK_PCT", 0.01)),
                    )
                    res = self.order_service.prepare_and_place(equity_usdt, req)
                    if res.accepted:
                        ctx.position_open = True
                        ctx.last_signal_ts = time.time()
                        # alimente FSM
                        side_enum = PositionSide.LONG if req.side == "long" else PositionSide.SHORT
                        st = self.pos.get(symbol) or PositionState(symbol, side_enum)
                        st.side = side_enum
                        st.status = PositionStatus.PENDING_ENTRY
                        st.entry_order_id = res.order_id or st.entry_order_id
                        st.req_qty = st.req_qty or (res.filled_qty or 0.0) or 0.0
                        st.sl = req.sl
                        st.tp = req.tp
                        self.pos[symbol] = st
                        print(f"[order] {symbol} accepted")
                        if self._tg.enabled():
                            await self._tg.send_message(f"Order accepted: {symbol} {req.side} @ {req.price}")
                    else:
                        print(f"[order] {symbol} rejected: {res.reason}")
                        if self._tg.enabled():
                            await self._tg.send_message(f"Order rejected: {symbol} reason={res.reason}")
                except Exception as e:
                    print(f"[trade-loop:{symbol}] order error: {e!r}")
            # 4) tempo
            await self._sleep(1.0)

    async def _task_sync_positions(self):
        print("[sync] start")
        while self._running:
            try:
                for symbol, st in list(self.pos.items()):
                    # PENDING_ENTRY -> consommer fills
                    if st.status == PositionStatus.PENDING_ENTRY and st.entry_order_id:
                        data = self.exchange.get_fills(symbol, order_id=st.entry_order_id)
                        for f in (data.get("data") or []):
                            fill = Fill(
                                order_id=str(f.get("orderId") or f.get("ordId") or ""),
                                trade_id=str(f.get("tradeId") or f.get("fillId") or f.get("execId") or ""),
                                price=float(f.get("price", f.get("fillPx", 0))),
                                qty=float(f.get("qty", f.get("fillSz", 0))),
                                fee=float(f.get("fee", f.get("fillFee", 0))),
                                ts=int(f.get("ts", f.get("time", 0))),
                            )
                            st.apply_fill_entry(fill)
                        # si toujours pas OPEN, vérifier positions visibles côté exchange
                        if st.status != PositionStatus.OPEN:
                            opens = self.exchange.get_open_positions(symbol).get("data", [])
                            for p in opens:
                                if p.get("symbol") == symbol and ((p.get("side") == "long") == (st.side == PositionSide.LONG)):
                                    st.status = PositionStatus.OPEN
                                    st.filled_qty = float(p.get("qty", st.filled_qty))
                                    st.avg_entry_price = float(p.get("avgEntryPrice", st.avg_entry_price))
                                    break
                        self.pos[symbol] = st
                    # OPEN -> vérifier si qty retombe à 0 (fermeture externe ou SL/TP)
                    elif st.status == PositionStatus.OPEN:
                        opens = self.exchange.get_open_positions(symbol).get("data", [])
                        qty_open = 0.0
                        for p in opens:
                            if p.get("symbol") == symbol and ((p.get("side") == "long") == (st.side == PositionSide.LONG)):
                                qty_open = float(p.get("qty", 0.0))
                                break
                        if qty_open <= 1e-12:
                            # regarder fills récents (sortie)
                            fills = self.exchange.get_fills(symbol).get("data", [])
                            for f in fills:
                                ts = int(f.get("ts", 0))
                                if st.opened_ts and ts >= st.opened_ts:
                                    fill = Fill(
                                        order_id=str(f.get("orderId") or ""),
                                        trade_id=str(f.get("tradeId") or f.get("fillId") or ""),
                                        price=float(f.get("price", 0)),
                                        qty=float(f.get("qty", 0)),
                                        fee=float(f.get("fee", 0)),
                                        ts=ts,
                                    )
                                    st.apply_fill_exit(fill)
                            if st.status != PositionStatus.CLOSED:
                                st.status = PositionStatus.CLOSED
                                st.closed_ts = int(time.time()*1000)
                            self.pos[symbol] = st
                    # PENDING_EXIT -> consommer fills de sortie
                    elif st.status == PositionStatus.PENDING_EXIT and st.exit_order_id:
                        data = self.exchange.get_fills(symbol, order_id=st.exit_order_id)
                        for f in (data.get("data") or []):
                            fill = Fill(
                                order_id=str(f.get("orderId") or ""),
                                trade_id=str(f.get("tradeId") or f.get("fillId") or ""),
                                price=float(f.get("price", 0)),
                                qty=float(f.get("qty", 0)),
                                fee=float(f.get("fee", 0)),
                                ts=int(f.get("ts", 0)),
                            )
                            st.apply_fill_exit(fill)
                        self.pos[symbol] = st
            except Exception as e:
                print(f"[sync] error: {e!r}")
            await self._sleep(2.0)

    # ---------- Helpers ops ----------
    def _equity_usdt(self) -> float:
        try:
            assets = self.exchange.get_assets()
            for a in (assets.get("data") or []):
                if a.get("currency") == "USDT":
                    return float(a.get("equity", 0))
        except Exception:
            pass
        return 0.0

    async def _flat_symbol(self, symbol: str):
        st = self.pos.get(symbol)
        if not st or st.status not in (PositionStatus.OPEN, PositionStatus.PENDING_ENTRY):
            return False, "no open position"
        side = "SELL" if st.side == PositionSide.LONG else "BUY"
        try:
            out = self.exchange.place_order(symbol=symbol, side=side, quantity=max(st.filled_qty, st.req_qty) or 0.0, order_type="market")
            st.exit_order_id = str((out.get("data") or {}).get("orderId", "")) if isinstance(out, dict) else st.exit_order_id
            st.status = PositionStatus.PENDING_EXIT
            self.pos[symbol] = st
            return True, "exit submitted"
        except Exception as e:
            return False, repr(e)

    async def _task_telegram(self):
        if not self._tg.enabled():
            while self._running:
                await self._sleep(2.0)
            return
        await self._tg.send_message(self._status_text())
        while self._running:
            try:
                updates = await self._tg.poll_commands(timeout_s=20)
                for u in updates:
                    text = u["text"].strip()
                    low = text.lower()
                    if low.startswith("/status"):
                        await self._tg.send_message(self._status_text())
                    elif low.startswith("/equity"):
                        await self._tg.send_message(f"Equity USDT: {self._equity_usdt():.2f}")
                    elif low.startswith("/pause"):
                        self._paused = True
                        await self._tg.send_message("Paused ✅ (no new entries)")
                    elif low.startswith("/resume"):
                        self._paused = False
                        await self._tg.send_message("Resumed ▶️")
                    elif low.startswith("/flat_all"):
                        oks = []
                        for s in list(self.pos.keys()):
                            ok, _ = await self._flat_symbol(s)
                            oks.append(f"{s}:{'ok' if ok else 'err'}")
                        await self._tg.send_message(" ".join(oks) or "none")
                    elif low.startswith("/flat"):
                        parts = text.split()
                        if len(parts) >= 2:
                            sym = parts[1].replace("_", "").upper()
                            ok, msg = await self._flat_symbol(sym)
                            await self._tg.send_message(f"{sym}: {msg}")
                        else:
                            await self._tg.send_message("Usage: /flat SYMBOL")
                    elif low.startswith("/symbols"):
                        parts = text.split(None, 1)
                        if len(parts) == 2:
                            new_syms = [s.strip().replace("_", "") for s in parts[1].split(",") if s.strip()]
                            if new_syms:
                                self.symbols = new_syms
                                for s in new_syms:
                                    if s not in self.ctx:
                                        self.ctx[s] = SymbolContext(s, [])
                                    if s not in self.pos:
                                        self.pos[s] = PositionState(s, PositionSide.LONG)
                                await self._tg.send_message(f"Symbols updated: {','.join(self.symbols)}")
                            else:
                                await self._tg.send_message("Usage: /symbols BTCUSDT,ETHUSDT")
                        else:
                            await self._tg.send_message("Usage: /symbols BTCUSDT,ETHUSDT")
                    elif low.startswith("/close"):
                        await self._tg.send_message("Closing…")
                        await self.stop(reason="telegram:/close")
                    else:
                        await self._tg.send_message(
                            "Commands: /status, /equity, /pause, /resume, /flat SYMBOL, /flat_all, /symbols SYM1,SYM2, /close")
            except asyncio.CancelledError:
                break
            except Exception:
                await self._sleep(2.0)

    # ---------- BOOT/RUN ----------
    async def run(self):
        if self._running:
            return
        self._running = True
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(reason=f"signal:{s.name}")))
            except NotImplementedError:
                pass  # Windows
        self._tasks = [
            asyncio.create_task(self._task_heartbeat(), name="heartbeat"),
            asyncio.create_task(self._task_refresh_watchlist(), name="watchlist"),
            asyncio.create_task(self._task_telegram(), name="telegram"),
            asyncio.create_task(self._task_sync_positions(), name="sync"),
        ] + [asyncio.create_task(self._task_trade_loop(s), name=f"trade:{s}") for s in self.symbols]
        print("[orchestrator] running")
        if self._tg.enabled():
            await self._tg.send_message("Orchestrator started ✅")
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
            t.cancel()
        await asyncio.sleep(0)  # yield to cancellations
        if self._tg.enabled():
            await self._tg.send_message(f"Orchestrator stopping: {reason}")


# Helper de lancement depuis bot.py
async def run_orchestrator(exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
    orch = Orchestrator(exchange, order_service, config, symbols)
    await orch.run()
