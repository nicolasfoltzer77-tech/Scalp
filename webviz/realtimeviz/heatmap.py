import asyncio
from datetime import datetime
from fastapi import APIRouter
from .models import HeatCell, HeatMapPayload

router = APIRouter()

# store[ (symbol, tf) ] = score
_store: dict[tuple[str, str], float] = {}
_lock = asyncio.Lock()


@router.get("/heatmap", response_model=HeatMapPayload)
async def heatmap_current():
    async with _lock:
        cells = [HeatCell(symbol=s, tf=tf, score=score)
                 for (s, tf), score in _store.items()]
    return HeatMapPayload(as_of=datetime.utcnow(), cells=cells)


@router.post("/heatmap/update", response_model=HeatMapPayload)
async def heatmap_update(payload: HeatMapPayload):
    """Met à jour les scores (utile pour brancher ton moteur ou pour tester)."""
    async with _lock:
        for cell in payload.cells:
            _store[(cell.symbol, cell.tf)] = float(cell.score)
    return await heatmap_current()


@router.post("/heatmap/demo", response_model=HeatMapPayload)
async def heatmap_demo():
    """Remplit la heatmap avec des valeurs de démo."""
    demo = [
        HeatCell(symbol="BTC/USDT", tf="1m", score=7.2),
        HeatCell(symbol="BTC/USDT", tf="5m", score=3.1),
        HeatCell(symbol="ETH/USDT", tf="1m", score=-4.8),
        HeatCell(symbol="ETH/USDT", tf="5m", score=0.5),
        HeatCell(symbol="SOL/USDT", tf="1m", score=9.3),
        HeatCell(symbol="SOL/USDT", tf="5m", score=6.7),
        HeatCell(symbol="XRP/USDT", tf="1m", score=-8.4),
    ]
    payload = HeatMapPayload(as_of=datetime.utcnow(), cells=demo)
    return await heatmap_update(payload)
