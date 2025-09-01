from __future__ import annotations
from decimal import Decimal
from sqlalchemy.orm import Session
from engine.storage.models import Position
D = Decimal
class PositionService:
    def __init__(self, db: Session): self.db = db
    def _get(self, symbol: str): return self.db.query(Position).filter_by(symbol=symbol).one_or_none()
    def apply_fill(self, symbol: str, side: str, price: float, amount: float, fee_cost: float = 0.0):
        pos = self._get(symbol); signed = D(str(amount)) if side=="buy" else -D(str(amount))
        px = D(str(price)); fee = D(str(fee_cost))
        if pos is None:
            pos = Position(symbol=symbol, qty=signed, entry_price=px, realized_pnl=D("0"))
            self.db.add(pos); self.db.commit(); return pos
        old_qty = D(str(pos.qty)); new_qty = old_qty + signed
        if old_qty == 0:
            pos.qty = new_qty; pos.entry_price = px
        elif (old_qty > 0 and signed > 0) or (old_qty < 0 and signed < 0):
            pos.entry_price = (D(str(pos.entry_price))*abs(old_qty) + px*abs(signed)) / abs(new_qty); pos.qty = new_qty
        else:
            closing_qty = min(abs(signed), abs(old_qty)); direction = D("1") if old_qty>0 else D("-1")
            pnl = (px - D(str(pos.entry_price))) * (closing_qty * direction)
            pos.realized_pnl = D(str(pos.realized_pnl)) + pnl - fee; pos.qty = new_qty
            if new_qty == 0: pos.entry_price = D("0")
        self.db.commit(); return pos
