# services/order_router.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Dict
from engine.position_tracker import PositionTracker
import uuid

Side = Literal["BUY","SELL"]
Mode = Literal["paper","real"]

@dataclass
class OrderResult:
    ok: bool
    position_id: Optional[str]
    info: Dict

class BaseOrderRouter:
    def __init__(self, mode: Mode = "paper"):
        self.mode = mode
    def open(self, *, symbol: str, side: Side, entry_price: float, qty: float, leverage: float,
             sl: float, tp1: float | None, tp2: float | None, notes: str | None = None) -> OrderResult:
        raise NotImplementedError
    def close(self, *, position_id: str, entry_price: float, close_price: float,
              qty: float, side: Literal["LONG","SHORT"]) -> OrderResult:
        raise NotImplementedError

class PaperOrderRouter(BaseOrderRouter):
    def __init__(self):
        super().__init__(mode="paper")
        self.tracker = PositionTracker()
    def open(self, **k) -> OrderResult:
        pos = self.tracker.open(
            position_id=str(uuid.uuid4()), symbol=k["symbol"], side=k["side"],
            entry_price=k["entry_price"], qty=k["qty"], leverage=k["leverage"],
            sl=k["sl"], tp1=k.get("tp1"), tp2=k.get("tp2"), notes=k.get("notes"),
        )
        return OrderResult(ok=True, position_id=pos.position_id, info={"status":"sim_open"})
    def close(self, **k) -> OrderResult:
        evt = self.tracker.close(
            position_id=k["position_id"], entry_price=k["entry_price"],
            close_price=k["close_price"], qty=k["qty"], side=k["side"]
        )
        return OrderResult(ok=True, position_id=k["position_id"], info={"status":"sim_close","evt":evt})

class RealOrderRouter(BaseOrderRouter):
    """Squelette pour exchange réel. Pour l’instant, on journalise l’intention via PositionTracker."""
    def __init__(self):
        super().__init__(mode="real")
        self.tracker = PositionTracker()
    def open(self, **k) -> OrderResult:
        pos = self.tracker.open(
            position_id=str(uuid.uuid4()), symbol=k["symbol"], side=k["side"],
            entry_price=k["entry_price"], qty=k["qty"], leverage=k["leverage"],
            sl=k["sl"], tp1=k.get("tp1"), tp2=k.get("tp2"),
            notes="REAL_INTENT: "+(k.get("notes") or "")
        )
        return OrderResult(ok=True, position_id=pos.position_id, info={"status":"real_intent_open"})
    def close(self, **k) -> OrderResult:
        evt = self.tracker.close(
            position_id=k["position_id"], entry_price=k["entry_price"],
            close_price=k["close_price"], qty=k["qty"], side=k["side"]
        )
        return OrderResult(ok=True, position_id=k["position_id"], info={"status":"real_intent_close","evt":evt})
