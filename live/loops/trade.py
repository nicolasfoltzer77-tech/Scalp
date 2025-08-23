# scalp/live/loops/trade.py
from __future__ import annotations
import asyncio, time, os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Callable

from ...services.utils import safe_call

QUIET = int(os.getenv("QUIET", "0") or "0")
PRINT_OHLCV_SAMPLE = int(os.getenv("PRINT_OHLCV_SAMPLE", "0") or "0")

# --- FSM ultra simple (à étendre si besoin)
class PositionFSM:
    def __init__(self):
        self.state = "FLAT"
        self.side = "flat"
        self.entry = 0.0
        self.qty = 0.0
    def can_open(self): return self.state == "FLAT"
    def on_open(self, side, entry, qty): self.state, self.side, self.entry, self.qty = "OPEN", side, entry, qty
    def can_close(self): return self.state == "OPEN"
    def on_close(self): self.state, self.side, self.entry, self.qty = "FLAT", "flat", 0.0, 0.0

@dataclass
class SymbolContext:
    symbol: str
    timeframe: str
    ohlcv: List[List[float]] = field(default_factory=list)
    ticks: int = 0
    fsm: PositionFSM = field(default_factory=PositionFSM)

class TradeLoop:
    """
    Boucle par symbole, indépendante de l'orchestrateur.
    """
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        ohlcv_fetch: Callable[..., Any],           # async fn(symbol, timeframe, limit) -> ohlcv
        order_market: Callable[..., Any],          # async fn(symbol, side, qty) -> order dict
        generate_signal: Callable[[List[List[float]], Dict[str, Any]], Dict[str, Any]],
        config: Dict[str, Any],
        mode_getter: Callable[[], str],
        log_signals, log_orders, log_fills,
        tick_counter_add: Callable[[int], None],
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.fetch = ohlcv_fetch
        self.order_market = order_market
        self.generate_signal = generate_signal
        self.config = config
        self.get_mode = mode_getter
        self.log_signals = log_signals
        self.log_orders = log_orders
        self.log_fills = log_fills
        self.ctx = SymbolContext(symbol, timeframe)
        self._tick_add = tick_counter_add

    async def run(self, running: Callable[[], bool]):
        lookback = 200
        while running():
            if self.get_mode() != "RUNNING":
                await asyncio.sleep(0.5); continue

            async def _fetch():
                return await self.fetch(self.symbol, timeframe=self.timeframe, limit=lookback+2)
            ohlcv = await safe_call(_fetch, label=f"fetch_ohlcv:{self.symbol}")
            if not ohlcv or len(ohlcv) < lookback+1:
                await asyncio.sleep(1.0); continue

            self.ctx.ohlcv = ohlcv
            self.ctx.ticks += 1
            self._tick_add(1)

            window = ohlcv[-(lookback+1):]
            ts, _o, _h, _l, c, _v = window[-1]

            try:
                sig = self.generate_signal(window, self.config) or {}
            except Exception as e:
                if not QUIET:
                    print(f"[trade:{self.symbol}] generate_signal error: {e}", flush=True)
                await asyncio.sleep(0.5); continue

            side = sig.get("side","flat"); entry = sig.get("entry", c); sl = sig.get("sl"); tp = sig.get("tp")
            self.log_signals.write_row({"ts": ts, "symbol": self.symbol, "side": side, "entry": entry, "sl": sl, "tp": tp, "last": c})

            # Entrée
            if self.ctx.fsm.state == "FLAT" and side in ("long","short"):
                balance = self.config.get("cash", 10_000.0)
                risk_pct = float(self.config.get("risk_pct", 0.5))
                notionnel = max(0.0, balance * risk_pct)
                qty = max(0.0, notionnel / max(entry or c, 1e-9))
                if qty > 0:
                    async def _place():
                        return await self.order_market(self.symbol, side, qty)
                    order = await safe_call(_place, label=f"order:{self.symbol}")
                    self.ctx.fsm.on_open(side, entry or c, qty)
                    self.log_orders.write_row({"ts": ts, "symbol": self.symbol, "side": side, "qty": qty,
                                               "status": "placed", "order_id": (order or {}).get("id",""), "note": "entry"})
            # Sortie
            elif self.ctx.fsm.state == "OPEN" and (side == "flat" or (side in ("long","short") and side != self.ctx.fsm.side)):
                qty = self.ctx.fsm.qty
                exit_side = "sell" if self.ctx.fsm.side == "long" else "buy"
                async def _close():
                    return await self.order_market(self.symbol, exit_side, qty)
                order = await safe_call(_close, label=f"close:{self.symbol}")
                self.log_orders.write_row({"ts": ts, "symbol": self.symbol, "side": exit_side, "qty": qty,
                                           "status": "placed", "order_id": (order or {}).get("id",""), "note": "exit"})
                self.log_fills.write_row({"ts": ts, "symbol": self.symbol, "side": exit_side, "price": c, "qty": qty,
                                          "order_id": (order or {}).get("id","")})
                self.ctx.fsm.on_close()

            if PRINT_OHLCV_SAMPLE and (self.ctx.ticks % 20 == 0) and not QUIET:
                print(f"[{self.symbol}] last={c} ticks={self.ctx.ticks}", flush=True)

            await asyncio.sleep(0.1 if QUIET else 0.01)