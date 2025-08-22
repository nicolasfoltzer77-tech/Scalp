from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from scalp.trade_utils import extract_available_balance


@dataclass
class OrderCaps:
    min_trade_usdt: float = 5.0
    leverage: float = 1.0


@dataclass
class OrderRequest:
    symbol: str
    side: str
    price: float
    sl: float
    tp: Optional[float]
    risk_pct: float


@dataclass
class OrderResult:
    accepted: bool
    reason: str = ""
    payload: Dict[str, Any] = None
    order_id: Optional[str] = None
    status: Optional[str] = None
    avg_price: Optional[float] = None
    filled_qty: Optional[float] = None


class Exchange(Protocol):
    def get_assets(self) -> Dict[str, Any]: ...
    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]: ...
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict[str, Any]: ...


class OrderService:
    def __init__(self, exchange: Exchange, caps: OrderCaps = OrderCaps()):
        self.exchange = exchange
        self.caps = caps

    @staticmethod
    def _abs(x: float) -> float:
        return -x if x < 0 else x

    def _calc_qty(self, equity_usdt: float, price: float, sl: float, risk_pct: float) -> float:
        dist = self._abs(price - sl)
        if dist <= 0:
            return 0.0
        risk_usdt = max(0.0, equity_usdt * risk_pct)
        return 0.0 if price <= 0 else (risk_usdt / dist)

    def prepare_and_place(self, equity_usdt: float, req: OrderRequest) -> OrderResult:
        qty = self._calc_qty(equity_usdt, req.price, req.sl, req.risk_pct)
        if qty <= 0:
            return OrderResult(False, "invalid_size")
        notional = qty * req.price
        if notional < self.caps.min_trade_usdt:
            return OrderResult(False, "under_min_notional")
        assets = self.exchange.get_assets()
        available = extract_available_balance(assets)
        required_margin = notional / max(1.0, self.caps.leverage)
        if available < required_margin:
            return OrderResult(False, "insufficient_margin")
        side = "BUY" if req.side == "long" else "SELL"
        out = self.exchange.place_order(
            symbol=req.symbol,
            side=side,
            quantity=qty,
            order_type="limit",
            price=req.price,
            stop_loss=req.sl,
            take_profit=req.tp,
        )
        oid = None
        status = None
        avg = None
        filled = None
        try:
            data = out.get("data") if isinstance(out, dict) else out
            if isinstance(data, dict):
                oid = str(data.get("orderId") or data.get("ordId") or data.get("id") or data.get("clientOid") or "")
                status = (data.get("status") or data.get("state") or "new").lower()
                avg = float(data.get("avgPrice", data.get("avgPx", 0)) or 0)
                filled = float(data.get("filledQty", data.get("fillSz", 0)) or 0)
        except Exception:
            pass
        return OrderResult(True, "", out, oid, status, avg, filled)
