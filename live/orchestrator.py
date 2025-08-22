from __future__ import annotations
import asyncio
import signal
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService, OrderRequest
from scalp.strategy import generate_signal, Signal


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

    # ---------- UTILITAIRES ----------
    async def _sleep(self, secs: float) -> None:
        try:
            await asyncio.sleep(secs)
        except asyncio.CancelledError:
            pass

    async def _safe(self, coro, *, label: str, backoff: float = 1.0, backoff_max: float = 30.0):
        delay = backoff
        while self._running:
            try:
                return await coro
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[orchestrator] {label} failed: {e!r}, retry in {delay:.1f}s")
                await self._sleep(delay)
                delay = min(backoff_max, delay * 1.7)

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
        # Fallback générique: on reconstitue une bougie synthétique à partir du ticker si pas d'API kline.
        try:
            data = self.exchange.get_kline(symbol, interval="1m")  # adapter si signature différente
            rows = data.get("data") or data.get("result") or []
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
        items = tkr.get("data") or []
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
        ctx.ohlcv = await self._safe(self._fetch_ohlcv_once(symbol, limit=200), label=f"fetch_ohlcv_boot:{symbol}")
        while self._running:
            # 1) rafraîchir dernière bougie
            new_rows = await self._safe(self._fetch_ohlcv_once(symbol, limit=2), label=f"fetch_ohlcv_tail:{symbol}")
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
                        ctx.position_open = True
                        ctx.last_signal_ts = time.time()
                        print(f"[order] {symbol} accepted")
                    else:
                        print(f"[order] {symbol} rejected: {res.reason}")
                except Exception as e:
                    print(f"[trade-loop:{symbol}] order error: {e!r}")
            # 4) tempo
            await self._sleep(1.0)

    async def _task_telegram(self):
        # Placeholder: déplacer ici la logique Telegram existante si nécessaire
        while self._running:
            await self._sleep(1.0)

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
        ] + [asyncio.create_task(self._task_trade_loop(s), name=f"trade:{s}") for s in self.symbols]
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
            t.cancel()
        await asyncio.sleep(0)  # yield to cancellations


# Helper de lancement depuis bot.py
async def run_orchestrator(exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
    orch = Orchestrator(exchange, order_service, config, symbols)
    await orch.run()
