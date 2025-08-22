from __future__ import annotations
import asyncio
import signal
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scalp.adapters.bitget import BitgetFuturesClient
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
        self.pos: Dict[str, PositionState] = {}
        # initialiser état par symbole
        for s in self.symbols:
            self.pos[s] = PositionState(symbol=s, side=PositionSide.LONG)  # side réel fixé à l’entrée
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._heartbeat_ts = 0.0
        self._paused = False
        self._tg = TelegramAsync(
            token=getattr(config, "TELEGRAM_BOT_TOKEN", None),
            chat_id=getattr(config, "TELEGRAM_CHAT_ID", None)
        )

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
        Récupère une petite fenêtre OHLCV via l'endpoint kline REST existant du client de base.
        On suppose que le client de base expose get_kline(symbol, granularity) -> dict avec "data".
        Adapte si nécessaire à ton client.
        """
        import time  # local import pour éviter dépendance implicite en haut de fichier
        # Fallback générique: on reconstitue une bougie synthétique à partir du ticker si pas d'API kline.
        try:
            data = self.exchange.get_kline(symbol, interval="1m")  # adapter si signature différente
            # data peut être un dict {"data": [...]} **ou** directement une list
            if isinstance(data, dict):
                rows = data.get("data") or data.get("result") or []
            else:
                rows = data or []
            out = []
            for r in rows[-limit:]:
                # Adapter les clés selon Bitget (ts, open, high, low, close, volume)
                o = float(r.get("open", r[1] if isinstance(r, (list, tuple)) else 0))
                h = float(r.get("high", r[2] if isinstance(r, (list, tuple)) else 0))
                l = float(r.get("low",  r[3] if isinstance(r, (list, tuple)) else 0))
                c = float(r.get("close",r[4] if isinstance(r, (list, tuple)) else 0))
                v = float(r.get("volume", r[5] if isinstance(r, (list, tuple)) else 0))
                t = int(r.get("ts", r[0] if isinstance(r, (list, tuple)) else 0))
                out.append({"ts": t, "open": o, "high": h, "low": l, "close": c, "volume": v})
            if out:
                return out
        except Exception:
            pass
        # Fallback synthétique
        tkr = self.exchange.get_ticker(symbol)
        items = (tkr.get("data") if isinstance(tkr, dict) else tkr) or []
        if not items:
            return []
        last = items[0]
        p = float(last.get("lastPrice", last.get("close", 0)))
        ts = int(time.time() * 1000)
        return [{"ts": ts, "open": p, "high": p, "low": p, "close": p, "volume": float(last.get("volume", 0))}]

    async def _task_trade_loop(self, symbol: str):
        ctx = self.ctx[symbol]
        print(f"[trade-loop] start {symbol}")
        # Pré-chargement fenêtre
        ctx.ohlcv = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=200),
                                     label=f"fetch_ohlcv_boot:{symbol}")
        while self._running:
            if self._paused:
                await self._sleep(1.0)
                continue
            # 1) rafraîchir dernière bougie
            new_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=2),
                                        label=f"fetch_ohlcv_tail:{symbol}")
            if new_rows:
                # maintenir une fenêtre glissante
                ctx.ohlcv = (ctx.ohlcv + new_rows)[-400:]
            # 2) générer signal
            try:
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
                        ctx.position_open = True  # legacy (peut rester pour logs)
                        ctx.last_signal_ts = time.time()
                        side_enum = PositionSide.LONG if req.side == "long" else PositionSide.SHORT
                        st = self.pos.get(symbol) or PositionState(symbol=symbol, side=side_enum)
                        st.side = side_enum
                        st.status = PositionStatus.PENDING_ENTRY
                        st.entry_order_id = res.order_id
                        st.req_qty = st.req_qty or 0.0
                        st.req_qty = max(st.req_qty, 0.0) + (res.filled_qty or 0.0) if (res.filled_qty or 0.0) > 0 else st.req_qty or 0.0
                        st.sl = float(getattr(req, "sl", 0)) or None
                        st.tp = float(getattr(req, "tp", 0)) or None
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
                    # 1) si PENDING_ENTRY -> consulter fills de l’order d’entrée
                    if st.status == PositionStatus.PENDING_ENTRY and st.entry_order_id:
                        fills = self.exchange.get_fills(symbol, order_id=st.entry_order_id).get("data", [])
                        for f in fills:
                            fill = Fill(order_id=f["orderId"], trade_id=f["tradeId"], price=float(f["price"]), qty=float(f["qty"]), fee=float(f.get("fee",0)), ts=int(f.get("ts",0)))
                            st.apply_fill_entry(fill)
                        # si toujours pas OPEN, vérifier statut ordre
                        if st.status == PositionStatus.PENDING_ENTRY:
                            orders = self.exchange.get_recent_orders(symbol).get("data", [])
                            for o in orders:
                                if o["orderId"] == st.entry_order_id:
                                    st.last_sync_ts = int(time.time()*1000)
                                    if o.get("status") in ("canceled","cancelled","rejected","expired"):
                                        # ordre tombé -> retour à IDLE
                                        st.status = PositionStatus.IDLE
                                        st.entry_order_id = None
                                    break
                    # 2) si OPEN -> vérifier si une position existe côté exchange
                    elif st.status == PositionStatus.OPEN:
                        # lire positions ouvertes
                        opens = self.exchange.get_open_positions(symbol).get("data", [])
                        open_qty = 0.0
                        avg = st.avg_entry_price
                        for p in opens:
                            if p["symbol"] == symbol and ((p["side"]=="long") == (st.side==PositionSide.LONG)):
                                open_qty = float(p["qty"])
                                avg = float(p.get("avgEntryPrice", avg))
                                break
                        st.avg_entry_price = avg or st.avg_entry_price
                        if open_qty <= 1e-12:
                            # position plus visible: soit fermée soit en fermeture
                            # vérifier fills de l’order de sortie si on en a un
                            if st.exit_order_id:
                                fills = self.exchange.get_fills(symbol, order_id=st.exit_order_id).get("data", [])
                                for f in fills:
                                    fill = Fill(order_id=f["orderId"], trade_id=f["tradeId"], price=float(f["price"]), qty=float(f["qty"]), fee=float(f.get("fee",0)), ts=int(f.get("ts",0)))
                                    st.apply_fill_exit(fill)
                            # si toujours pas CLOSED, tenter une lecture des fills récents (sans order_id)
                            if st.status != PositionStatus.CLOSED:
                                fills = self.exchange.get_fills(symbol).get("data", [])
                                # garder uniquement ceux après opened_ts
                                for f in fills:
                                    if st.opened_ts and int(f.get("ts",0)) >= st.opened_ts:
                                        # heuristique: sens inverse pour fermeture
                                        qty = float(f["qty"])
                                        side_exec = "buy" if qty < 0 else "sell"  # placeholder si l’API a le signe
                                # Si aucune info, marquer CLOSED de façon conservatrice (à défaut)
                                st.status = PositionStatus.CLOSED
                                st.closed_ts = int(time.time()*1000)
                        else:
                            # mettre en cohérence la qty locale avec l’exchange
                            st.filled_qty = open_qty
                    # 3) si PENDING_EXIT -> consommer fills de l’order de sortie
                    elif st.status == PositionStatus.PENDING_EXIT and st.exit_order_id:
                        fills = self.exchange.get_fills(symbol, order_id=st.exit_order_id).get("data", [])
                        for f in fills:
                            fill = Fill(order_id=f["orderId"], trade_id=f["tradeId"], price=float(f["price"]), qty=float(f["qty"]), fee=float(f.get("fee",0)), ts=int(f.get("ts",0)))
                            st.apply_fill_exit(fill)
                    st.last_sync_ts = int(time.time()*1000)
                    self.pos[symbol] = st
            except Exception as e:
                print(f"[sync] error: {e!r}")
            await self._sleep(2.0)

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
                    elif low.startswith("/pause"):
                        self._paused = True
                        await self._tg.send_message("Paused ✅ (no new entries)")
                    elif low.startswith("/resume"):
                        self._paused = False
                        await self._tg.send_message("Resumed ▶️")
                    elif low.startswith("/symbols"):
                        parts = text.split(None, 1)
                        if len(parts) == 2:
                            new_syms = [s.strip().replace("_", "") for s in parts[1].split(",") if s.strip()]
                            if new_syms:
                                self.symbols = new_syms
                                for s in new_syms:
                                    if s not in self.ctx:
                                        self.ctx[s] = SymbolContext(s, [])
                                await self._tg.send_message(f"Symbols updated: {','.join(self.symbols)}")
                            else:
                                await self._tg.send_message("Usage: /symbols BTCUSDT,ETHUSDT")
                        else:
                            await self._tg.send_message("Usage: /symbols BTCUSDT,ETHUSDT")
                    elif low.startswith("/close"):
                        await self._tg.send_message("Closing…")
                        await self.stop(reason="telegram:/close")
                    else:
                        await self._tg.send_message("Commands: /status, /pause, /resume, /symbols SYM1,SYM2, /close")
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
