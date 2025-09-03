from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# -------- Realtime events --------
class Signal(BaseModel):
    type: Literal["signal"] = "signal"
    ts: datetime
    symbol: str
    side: Literal["buy", "sell"]
    score: float
    timeframe: str
    rules: List[str]

class Position(BaseModel):
    type: Literal["position"] = "position"
    ts_open: datetime
    ts_update: datetime
    symbol: str
    side: Literal["long", "short"]
    qty: float
    avg_price: float
    upnl: float
    leverage: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: Literal["open", "closed"] = "open"

# -------- Heatmap --------
class HeatCell(BaseModel):
    symbol: str
    tf: str = Field(..., description="timeframe ex: 1m / 5m / 15m")
    score: float = Field(..., ge=-10.0, le=10.0)  # -10 sell .. +10 buy

class HeatMapPayload(BaseModel):
    as_of: datetime
    cells: List[HeatCell]
