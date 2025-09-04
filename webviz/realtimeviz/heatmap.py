from datetime import datetime, timezone
from random import random
from .models import Heatmap, HeatmapCell

SYMS = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSDT", "ETHUSDT", "XAUUSD"]

def build_dummy_heatmap() -> Heatmap:
    cells = []
    for s in SYMS:
        sc = round((random() * 2 - 1) * 100, 2)
        side = "BUY" if sc > 25 else "SELL" if sc < -25 else "FLAT"
        cells.append(HeatmapCell(sym=s, score=sc, side=side))
    return Heatmap(as_of=datetime.now(timezone.utc), cells=cells)
