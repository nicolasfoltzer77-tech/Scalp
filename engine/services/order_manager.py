from __future__ import annotations
from typing import Any, Dict
from sqlalchemy.orm import Session
from engine.storage.models import Order, OrderStatus, Trade
from engine.services.position_service import PositionService
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter

def _lower(x): return (x or "").lower()

class OrderManager:
    def __init__(self, db: Session, adapter: CcxtBitgetAdapter):
        self.db = db
        self.adapter = adapter
        self.pos = PositionService(db)

    def place(self, symbol: str, side: str, type_: str, amount: float,
              price: float | None = None, *, reduce_only: bool = False,
              params: Dict[str, Any] | None = None) -> Order:
        order = self.adapter.create_order(symbol, side, type_, amount, price,
                                          reduce_only=reduce_only, params=params or {})
        o = Order(
            exchange="bitget", symbol=symbol, side=side, type=type_,
            status=OrderStatus.open_, amount=amount, price=price,
            client_oid=order.get("clientOrderId") or order.get("clientOid") or "",
            exchange_order_id=order.get("id") or order.get("orderId") or "",
            reduce_only=reduce_only,
        )
        self.db.add(o); self.db.commit()
        self.refresh_from_exchange(o)
        return o

    def refresh_from_exchange(self, o: Order):
        data = self.adapter.fetch_order(o.exchange_order_id, o.symbol)
        status = _lower(data.get("status"))
        filled = float(data.get("filled") or 0)
        avg_px = data.get("average") or data.get("priceAvg") or data.get("info", {}).get("priceAvg")
        if status in ("closed", "canceled"):
            o.status = OrderStatus.closed if status == "closed" else OrderStatus.canceled
        elif filled > 0:
            o.status = OrderStatus.partially_filled
        o.filled = filled
        if avg_px is not None:
            o.avg_price = float(avg_px)
        self.db.commit()

        trades = self.adapter.fetch_my_trades(o.symbol, params={"orderId": o.exchange_order_id})
        for t in trades:
            ex_tid = t.get("id") or t.get("tradeId")
            exists = ex_tid and self.db.query(Trade).filter_by(exchange_trade_id=ex_tid).one_or_none()
            if exists: continue
            fee = (t.get("fee") or {})
            tr = Trade(
                order_id=o.id, symbol=o.symbol, side=t["side"], price=float(t["price"]),
                amount=float(t["amount"]), fee_currency=fee.get("currency"),
                fee_cost=float(fee.get("cost") or 0), is_maker=(t.get("takerOrMaker")=="maker"),
                exchange_trade_id=ex_tid
            )
            self.db.add(tr)
            self.pos.apply_fill(o.symbol, t["side"], float(t["price"]), float(t["amount"]),
                                float(fee.get("cost") or 0.0))
        self.db.commit()

    def reconcile_open_orders(self):
        open_orders = self.adapter.fetch_open_orders()
        open_ids = {oo.get("id") for oo in open_orders if oo.get("id")}
        for o in self.db.query(Order).filter(Order.status.in_([OrderStatus.open_, OrderStatus.partially_filled])):
            if o.exchange_order_id not in open_ids:
                self.refresh_from_exchange(o)
