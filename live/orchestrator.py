# live/orchestrator.py
from __future__ import annotations

import asyncio
import signal
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

# --- Dépendances internes (tolérance si modules optionnels manquent) ---
from scalp.adapters.bitget import BitgetFuturesClient
try:
    from live.telegram_async import TelegramAsync  # déjà ajouté précédemment
except Exception:  # pas bloquant
    TelegramAsync = None  # type: ignore

try:
    # Adaptateur OHLCV/ticker normalisé (si présent)
    from scalp.adapters.market_data import MarketData
except Exception:
    MarketData = None  # type: ignore

from scalp.services.order_service import OrderService, OrderRequest
from scalp.strategy import generate_signal, Signal


# -------------------- Types simples --------------------
@dataclass
class SymbolContext:
    symbol: str
    ohlcv: List[Dict[str, float]]  # liste de dicts normalisés
    position_open: bool = False
    last_signal_ts: float = 0.0


# =======================================================
#                 ORCHESTRATEUR ASYNC
# =======================================================
class Orchestrator:
    """
    Orchestrateur asyncio minimal, robuste aux variations de format des données OHLCV.
    - Heartbeat
    - Rafraîchissement watchlist (placeholder)
    - Trade loop par symbole
    - (Optionnel) Telegram si TELEGRAM_* fournis
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
        self._paused = False

        # Telegram (facultatif)
        if TelegramAsync is not None:
            token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
            chat = getattr(config, "TELEGRAM_CHAT_ID", None)
            self._tg = TelegramAsync(token=token, chat_id=chat)
        else:
            self._tg = None

        # MarketData (normalisation OHLCV)
        self._md = MarketData(self.exchange) if MarketData is not None else None

    # ----------------- Utilitaires communs -----------------
    async def _sleep(self, secs: float) -> None:
        try:
            await asyncio.sleep(secs)
        except asyncio.CancelledError:
            pass

    async def _safe(self, coro_factory, *, label: str, backoff: float = 1.0, backoff_max: float = 30.0):
        """
        Exécute une fabrique de coroutine avec retry exponentiel.
        Evite 'cannot reuse already awaited coroutine' (toujours créer un nouveau coroutine).
        """
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

    # ----------------- Normalisation OHLCV -----------------
    def _normalize_rows(self, rows: Any) -> List[Dict[str, float]]:
        """
        Garantit une liste de dicts: {'ts','open','high','low','close','volume'}
        Accepte list[dict] OU list[list/tuple] OU None.
        """
        out: List[Dict[str, float]] = []
        if not rows:
            return out

        for r in rows:
            if isinstance(r, dict):
                ts = int(r.get("ts") or r.get("time") or r.get("timestamp") or 0)
                o = float(r.get("open", 0.0))
                h = float(r.get("high", o))
                l = float(r.get("low", o))
                c = float(r.get("close", o))
                v = float(r.get("volume", r.get("vol", 0.0)))
            else:
                rr = list(r)
                # Formats courants: [ts,o,h,l,c,v] ou [o,h,l,c,v,ts]
                if len(rr) >= 6 and isinstance(rr[0], (int, float)) and rr[0] > 10**10:
                    ts, o, h, l, c = int(rr[0]), float(rr[1]), float(rr[2]), float(rr[3]), float(rr[4])
                    v = float(rr[5])
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
        """
        Prépare 3 représentations pour satisfaire generate_signal selon sa signature:
        1) list[dict]  : notre format normalisé
        2) list[list]  : [[ts,o,h,l,c,v], ...]
        3) dict colonnes: {'open':[...], 'high':[...], 'low':[...], 'close':[...], 'volume':[...]}
        """
        rd = self._normalize_rows(rows_any or [])
        rl = [[r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]] for r in rd]
        cols = {"ts": [], "open": [], "high": [], "low": [], "close": [], "volume": []}
        for r in rd:
            cols["ts"].append(r["ts"])
            cols["open"].append(r["open"])
            cols["high"].append(r["high"])
            cols["low"].append(r["low"])
            cols["close"].append(r["close"])
            cols["volume"].append(r["volume"])
        return rd, rl, cols

    # ------------- Lecture OHLCV normalisée -------------
    async def _fetch_ohlcv_once(self, symbol: str, limit: int = 100) -> List[Dict[str, float]]:
        """
        Lecture via MarketData si dispo; sinon, tentative via exchange.get_kline puis fallback ticker.
        Toujours retourne List[Dict].
        """
        # 1) Adaptateur MarketData (préféré)
        if self._md is not None:
            try:
                d = await self._safe(
                    lambda: asyncio.to_thread(self._md.get_ohlcv, symbol, "1m", limit),
                    label=f"md.get_ohlcv:{symbol}",
                )
                if isinstance(d, dict) and d.get("success") and d.get("data"):
                    return self._normalize_rows(d["data"])
            except Exception:
                pass

        # 2) Exchange direct (formats arbitraires)
        rows: List[Any] = []
        try:
            data = await self._safe(lambda: asyncio.to_thread(self.exchange.get_kline, symbol, interval="1m"),
                                    label=f"get_kline:{symbol}")
        except Exception:
            data = None

        if isinstance(data, dict):
            rows = (
                data.get("data") or data.get("result") or data.get("records")
                or data.get("list") or data.get("items") or data.get("candles") or []
            )
            # déballage si encore un dict imbriqué
            guard = 0
            while isinstance(rows, dict) and guard < 3:
                rows = (
                    rows.get("data") or rows.get("result") or rows.get("records")
                    or rows.get("list") or rows.get("items") or rows.get("candles") or rows.get("klines") or rows.get("bars") or []
                )
                guard += 1
        elif isinstance(data, (list, tuple)):
            rows = list(data)

        out = self._normalize_rows(rows)[-limit:]
        if out:
            return out

        # 3) Fallback strict via ticker → bougie synthétique
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
                    vol = float(last.get("volume", last.get("usdtVolume", last.get("quoteVolume", 0.0))))
                else:
                    seq = list(last)
                    # heuristique indices
                    if len(seq) >= 5:
                        first_is_ts = isinstance(seq[0], (int, float)) and seq[0] > 10**10
                        if first_is_ts:
                            p = float(seq[4])
                            vol = float(seq[5]) if len(seq) > 5 else 0.0
                        else:
                            p = float(seq[3]) if len(seq) > 3 else float(seq[-2])
                            vol = float(seq[4]) if len(seq) > 4 else float(seq[-1])
                    else:
                        p, vol = float(seq[-1]) if seq else 0.0, 0.0
                ts = int(time.time() * 1000)
                return [{"ts": ts, "open": p, "high": p, "low": p, "close": p, "volume": vol}]
        except Exception:
            pass
        return []

    # ----------------- Tâches principales -----------------
    async def _task_heartbeat(self):
        while self._running:
            self._heartbeat_ts = time.time()
            print("[heartbeat] alive")
            await self._sleep(15)

    async def _task_refresh_watchlist(self):
        # Placeholder: implémente ici le filtrage de paires si nécessaire
        while self._running:
            await self._sleep(60)

    def _status_text(self) -> str:
        alive = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._heartbeat_ts)) if self._heartbeat_ts else "n/a"
        syms = ",".join(self.symbols) or "-"
        return (f"Scalp bot\nrunning: {self._running}\npaused: {self._paused}\n"
                f"heartbeat: {alive}\nsymbols: {syms}")

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
                    elif low.startswith("/symbols"):
                        parts = text.split(None, 1)
                        if len(parts) == 2:
                            syms = [s.strip().replace("_", "") for s in parts[1].split(",") if s.strip()]
                            if syms:
                                self.symbols = syms
                                for s in syms:
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

    async def _task_trade_loop(self, symbol: str):
        ctx = self.ctx[symbol]
        print(f"[trade-loop] start {symbol}")

        # Boot: fenêtre initiale
        boot_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=200),
                                     label=f"fetch_ohlcv_boot:{symbol}")
        ctx.ohlcv = self._normalize_rows(boot_rows or [])
        if ctx.ohlcv:
            # log de contrôle une seule fois
            print(f"[debug:{symbol}] ohlcv sample -> dict={list(ctx.ohlcv[0].keys())}")

        while self._running:
            if self._paused:
                await self._sleep(1.0)
                continue

            # Rafraîchi
            new_rows = await self._safe(lambda: self._fetch_ohlcv_once(symbol, limit=2),
                                        label=f"fetch_ohlcv_tail:{symbol}")
            if new_rows:
                ctx.ohlcv = (self._normalize_rows(ctx.ohlcv) + self._normalize_rows(new_rows))[-400:]

            # Générer signal (fallback 3 formats)
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
                            head_t = type(ctx.ohlcv).__name__
                            first_t = type(ctx.ohlcv[0]).__name__ if ctx.ohlcv else "empty"
                            print(f"[trade-loop:{symbol}] generate_signal error: {e3!r} (fallback after {e1!r} / {e2!r}) rows={head_t}/{first_t}")
                            sig = None
            except Exception as e:
                print(f"[trade-loop:{symbol}] normalize error: {e!r}")
                sig = None

            # Exécuter si signal et pas de position ouverte
            if sig and not ctx.position_open:
                try:
                    assets = await self._safe(lambda: asyncio.to_thread(self.exchange.get_assets),
                                              label="get_assets")
                    equity_usdt = 0.0
                    if isinstance(assets, dict):
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
            *(
                asyncio.create_task(self._task_trade_loop(s), name=f"trade:{s}")
                for s in self.symbols
            )
        ]
        # Telegram si dispo
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
        if not self._running:
            return
        print(f"[orchestrator] stopping: {reason}")
        self._running = False
        for t in self._tasks:
            try:
                t.cancel()
            except Exception:
                pass
        await asyncio.sleep(0)  # yield to cancellations


# Helper de lancement depuis bot.py
async def run_orchestrator(exchange: BitgetFuturesClient, order_service: OrderService, config, symbols: Sequence[str]):
    orch = Orchestrator(exchange, order_service, config, symbols)
    await orch.run()