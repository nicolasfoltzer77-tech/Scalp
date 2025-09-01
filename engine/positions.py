# engine/positions.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Dict
import json

Status = Literal["OPEN", "UPDATE", "CLOSE"]

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _write_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

@dataclass
class Position:
    position_id: str
    ts: str
    symbol: str
    side: Literal["LONG","SHORT"]
    entry_price: float
    qty: float
    leverage: float
    sl: float
    tp1: float | None = None
    tp2: float | None = None
    fees_open: float = 0.0
    realized_pnl: float = 0.0
    status: Status = "OPEN"
    notes: Optional[str] = None

class PositionTracker:
    """
    Journalisation append-only des positions et trades.
    """

    def __init__(self, base_dir: Path = Path("var"), taker_fee_bps: int = 8):
        # ex: 0.0008 -> 8 bps
        self.base_dir = base_dir
        self.taker_fee = taker_fee_bps / 10000.0

    def _positions_path(self) -> Path:
        d = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.base_dir / "positions" / d / "positions.jsonl"

    def _trades_path(self) -> Path:
        d = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.base_dir / "trades" / d / "trades.jsonl"

    def open(self, *, position_id: str, symbol: str, side: Literal["BUY","SELL"], entry_price: float, qty: float, leverage: float, sl: float, tp1: float | None, tp2: float | None, notes: str | None = None) -> Position:
        notional = entry_price * qty * leverage
        fees = notional * self.taker_fee
        pos = Position(
            position_id=position_id, ts=_utcnow(), symbol=symbol,
            side="LONG" if side == "BUY" else "SHORT",
            entry_price=entry_price, qty=qty, leverage=leverage,
            sl=sl, tp1=tp1, tp2=tp2,
            fees_open=fees, realized_pnl=-fees, status="OPEN", notes=notes
        )
        _write_jsonl(self._positions_path(), asdict(pos))
        _write_jsonl(self._trades_path(), {"ts": pos.ts, "type": "OPEN", "position_id": position_id, "symbol": symbol, "side": pos.side, "price": entry_price, "qty": qty, "fees": fees})
        return pos

    def update(self, position_id: str, **fields) -> None:
        evt = {"ts": _utcnow(), "type": "UPDATE", "position_id": position_id, **fields}
        _write_jsonl(self._positions_path(), evt)

    def close(self, *, position_id: str, entry_price: float, close_price: float, qty: float, side: Literal["LONG","SHORT"]) -> Dict:
        notional = close_price * qty
        fees = notional * self.taker_fee
        if side == "LONG":
            gross = (close_price - entry_price) * qty
        else:
            gross = (entry_price - close_price) * qty
        realized = gross - fees
        evt = {
            "ts": _utcnow(), "type": "CLOSE", "position_id": position_id,
            "price": close_price, "qty": qty, "fees": fees,
            "side": side, "realized_pnl_delta": realized
        }
        _write_jsonl(self._trades_path(), evt)
        _write_jsonl(self._positions_path(), evt)
        return evt
