from pydantic import BaseModel, Field
from typing import List

class HeatCell(BaseModel):
    x: int
    y: int
    v: float = Field(..., description="value")

class Heatmap(BaseModel):
    as_of: str
    cells: List[HeatCell]
