from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel

Side = Literal["BUY", "SELL", "FLAT"]

class HeatmapCell(BaseModel):
    sym: str
    score: float
    side: Side = "FLAT"
    qty: Optional[int] = None

class Heatmap(BaseModel):
    as_of: datetime
    cells: List[HeatmapCell]
