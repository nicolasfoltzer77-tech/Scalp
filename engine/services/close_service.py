from __future__ import annotations
from sqlalchemy.orm import Session
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter
from engine.services.order_manager import OrderManager
from engine.storage.models import Position
class CloseService:
    def __init__(self, db: Session, adapter: CcxtBitgetAdapter):
        self.db, self.adapter = db, adapter; self.om = OrderManager(db, adapter)
    def close_symbol_market(self, symbol: str):
        pos = self.db.query(Position).filter_by(symbol=symbol).one_or_none()
        if not pos or float(pos.qty) == 0.0: return None
        qty = abs(float(pos.qty)); side = "sell" if float(pos.qty) > 0 else "buy"
        return self.om.place(symbol, side, "market", qty, reduce_only=True)
