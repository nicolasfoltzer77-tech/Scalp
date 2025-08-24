from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional
import time

class PositionStatus(Enum):
    IDLE = auto()
    PENDING_ENTRY = auto()
    OPEN = auto()
    PENDING_EXIT = auto()
    CLOSED = auto()

class PositionSide(Enum):
    LONG = 1
    SHORT = -1

@dataclass
class Fill:
    order_id: str
    trade_id: str
    price: float
    qty: float
    fee: float
    ts: int

@dataclass
class PositionState:
    symbol: str
    side: PositionSide
    status: PositionStatus = PositionStatus.IDLE
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None
    req_qty: float = 0.0
    filled_qty: float = 0.0
    avg_entry_price: float = 0.0
    avg_exit_price: float = 0.0
    sl: Optional[float] = None
    tp: Optional[float] = None
    realized_pnl: float = 0.0
    fees: float = 0.0
    opened_ts: Optional[int] = None
    closed_ts: Optional[int] = None
    fills: List[Fill] = field(default_factory=list)
    last_sync_ts: int = field(default_factory=lambda: int(time.time()*1000))

    def apply_fill_entry(self, f: Fill) -> None:
        self.fills.append(f)
        self.filled_qty += f.qty
        # moyenne pondérée
        notional = self.avg_entry_price * (self.filled_qty - f.qty) + f.price * f.qty
        self.avg_entry_price = notional / max(1e-12, self.filled_qty)
        self.fees += abs(f.fee)
        if self.opened_ts is None:
            self.opened_ts = f.ts
        if self.filled_qty > 1e-12:
            self.status = PositionStatus.OPEN

    def apply_fill_exit(self, f: Fill) -> None:
        self.fills.append(f)
        qty = min(self.filled_qty, f.qty)
        # realized pnl sur la quantité fermée
        if self.side == PositionSide.LONG:
            self.realized_pnl += (f.price - self.avg_entry_price) * qty
        else:
            self.realized_pnl += (self.avg_entry_price - f.price) * qty
        self.fees += abs(f.fee)
        self.filled_qty = max(0.0, self.filled_qty - qty)
        # moyenne de sortie indicative
        closed_q = (self.req_qty - self.filled_qty)
        self.avg_exit_price = ((self.avg_exit_price * (closed_q - qty)) + f.price * qty) / max(1e-12, closed_q)
        if self.filled_qty <= 1e-12:
            self.status = PositionStatus.CLOSED
            self.closed_ts = f.ts

