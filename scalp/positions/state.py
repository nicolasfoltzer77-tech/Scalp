from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional
import time

class PositionStatus(Enum):
    IDLE = auto()          # aucune position ni ordre actif
    PENDING_ENTRY = auto() # ordre d'entrée live mais pas encore rempli
    OPEN = auto()          # position ouverte sur l'exchange
    PENDING_EXIT = auto()  # fermeture en cours (ordre placé)
    CLOSED = auto()        # position fermée (avec realized_pnl)

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
    # ordres
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None
    # quantités/prix
    req_qty: float = 0.0
    filled_qty: float = 0.0
    avg_entry_price: float = 0.0
    avg_exit_price: float = 0.0
    # stops
    sl: Optional[float] = None
    tp: Optional[float] = None
    # PnL/fees
    realized_pnl: float = 0.0
    fees: float = 0.0
    # journal
    fills: List[Fill] = field(default_factory=list)
    opened_ts: Optional[int] = None
    closed_ts: Optional[int] = None
    last_sync_ts: int = field(default_factory=lambda: int(time.time()*1000))

    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN

    def is_idle(self) -> bool:
        return self.status == PositionStatus.IDLE

    def apply_fill_entry(self, f: Fill) -> None:
        self.fills.append(f)
        new_notional = self.avg_entry_price * self.filled_qty + f.price * f.qty
        self.filled_qty += f.qty
        self.avg_entry_price = new_notional / max(1e-12, self.filled_qty)
        self.fees += abs(f.fee)
        if self.filled_qty >= self.req_qty - 1e-12:
            self.status = PositionStatus.OPEN
            self.opened_ts = f.ts

    def apply_fill_exit(self, f: Fill) -> None:
        self.fills.append(f)
        exit_notional = self.avg_exit_price * (self.req_qty - max(0.0, self.filled_qty)) + f.price * f.qty
        # Ici on calcule le realized pnl au fil de l’eau sur qty exécutée
        qty_to_close = f.qty
        side_sign = 1.0 if self.side == PositionSide.LONG else -1.0
        pnl = side_sign * (f.price - self.avg_entry_price) * qty_to_close * -1.0
        # Pour un long: vendre (exit) -> realized = (exit - entry) * qty
        pnl = (f.price - self.avg_entry_price) * qty_to_close if self.side == PositionSide.LONG else (self.avg_entry_price - f.price) * qty_to_close
        self.realized_pnl += pnl
        self.fees += abs(f.fee)
        # On décrémente filled_qty restante (position)
        self.filled_qty = max(0.0, self.filled_qty - qty_to_close)
        self.avg_exit_price = exit_notional / max(1e-12, self.req_qty)
        if self.filled_qty <= 1e-12:
            self.status = PositionStatus.CLOSED
            self.closed_ts = f.ts
