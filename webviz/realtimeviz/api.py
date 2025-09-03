import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .models import Signal, Position
from datetime import datetime

router = APIRouter()
connections: list[WebSocket] = []
event_queue: asyncio.Queue = asyncio.Queue()


async def broadcaster():
    """Task to broadcast messages from the queue to all connected clients."""
    while True:
        event = await event_queue.get()
        to_remove = []
        for ws in connections:
            try:
                await ws.send_json(event)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            connections.remove(ws)


@router.websocket("/ws/stream")
async def stream(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        connections.remove(websocket)


# Exemple d’injection d’événements (à utiliser ailleurs dans le code du bot)
async def send_test_signal():
    event = Signal(
        ts=datetime.utcnow(),
        symbol="BTC/USDT",
        side="buy",
        score=7.2,
        timeframe="1m",
        rules=["ema_fast>ema_slow", "volatility_ok"]
    ).dict()
    await event_queue.put(event)
