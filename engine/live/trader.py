# engine/live/trader.py
from __future__ import annotations
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

@dataclass
class Position:
    symbol: str
    tf: str
    side: str = "flat"   # "long" | "flat"
    entry: float = 0.0
    size: float = 0.0
    trail: Optional[float] = None

class OrderLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(["ts","symbol","tf","action","price","size","reason"])

    def _write(self, row: Sequence[str | float | int]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(",".join(str(x).replace(",", " ") for x in row) + "\n")

    def log(self, **kw) -> None:
        self._write([kw.get("ts", int(time.time()*1000)), kw["symbol"], kw["tf"],
                     kw["action"], kw.get("price", 0.0), kw.get("size", 0.0),
                     kw.get("reason","")])

class Trader:
    """
    Gère un état de position très simple (one-way, long only) + logs, et passe
    aux ordres réels si paper_trade=False.
    """
    def __init__(self, *, paper_trade: bool, client: Any | None, order_logger: OrderLogger) -> None:
        self.paper = paper_trade
        self.client = client
        self.log = order_logger
        self.state: Dict[tuple[str,str], Position] = {}

    def _pos(self, symbol: str, tf: str) -> Position:
        key = (symbol, tf)
        if key not in self.state:
            self.state[key] = Position(symbol=symbol, tf=tf)
        return self.state[key]

    def _order_real_market(self, symbol: str, side: str, size: float) -> None:
        if not self.client:
            return
        try:
            self.client.place_market_order_one_way(symbol, side, size)
        except Exception:
            # on se contente de logguer; l'orchestrateur poursuit
            pass

    def compute_size(self, equity: float, price: float, atr: float, risk_pct: float) -> float:
        # risk par unité ~ ATR (garde-fou min)
        risk_per_unit = max(atr, price * 0.002)
        risk_cash = max(0.0, equity * risk_pct)
        units = risk_cash / risk_per_unit if risk_per_unit > 0 else 0.0
        return max(0.0, round(units, 6))

    def on_signal(self, *, symbol: str, tf: str, price: float, atr: float,
                  params: Dict[str, float], signal_now: int, signal_prev: int,
                  equity: float = 10_000.0, ts: int | None = None) -> None:
        ts = ts or int(time.time() * 1000)
        p = self._pos(symbol, tf)
        trail_mult = float(params.get("trail_atr_mult", 2.0))
        risk_pct = float(params.get("risk_pct_equity", 0.02))
        if p.side == "flat":
            if signal_prev <= 0 and signal_now > 0:
                size = self.compute_size(equity, price, atr, risk_pct)
                p.side = "long"; p.entry = price; p.size = size
                p.trail = price - trail_mult * atr if atr > 0 else None
                self.log.log(ts=ts, symbol=symbol, tf=tf, action="BUY", price=price, size=size, reason="ema_cross_up")
                if not self.paper and size > 0:
                    self._order_real_market(symbol, "buy", size)
        else:
            # update trailing stop
            new_trail = price - trail_mult * atr if atr > 0 else None
            if new_trail is not None and (p.trail is None or new_trail > p.trail):
                p.trail = new_trail
            # sortie par signal inverse ou par cassure du trail
            exit_by_signal = (signal_prev >= 0 and signal_now < 0)
            exit_by_trail = (p.trail is not None and price < p.trail)
            if exit_by_signal or exit_by_trail:
                self.log.log(ts=ts, symbol=symbol, tf=tf, action="SELL", price=price, size=p.size,
                             reason="ema_cross_down" if exit_by_signal else "trail_hit")
                if not self.paper and p.size > 0:
                    self._order_real_market(symbol, "sell", p.size)
                # flat
                self.state[(symbol, tf)] = Position(symbol=symbol, tf=tf)