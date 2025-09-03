import asyncio, json, time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .models import Signal

router = APIRouter()

_clients: set[WebSocket] = set()
_queue: asyncio.Queue[str] = asyncio.Queue()
_lock = asyncio.Lock()

@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    async with _lock:
        _clients.add(ws)
    try:
        # petit hello
        await ws.send_text(json.dumps({"type":"hello","ts":time.time()}))
        while True:
            # on ignore ce que le client envoie, mais on garde la socket vivante
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with _lock:
            _clients.discard(ws)

async def broadcaster():
    """Diffusion des messages de _queue à tous les clients connectés."""
    while True:
        msg = await _queue.get()
        dead = []
        for ws in list(_clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        if dead:
            async with _lock:
                for ws in dead:
                    _clients.discard(ws)

async def send_test_signal():
    """Envoie un signal de test au démarrage (pour vérif rapide)."""
    await asyncio.sleep(1.0)
    s = Signal(
        ts = __import__("datetime").datetime.utcnow(),
        symbol = "BTC/USDT",
        side = "buy",
        score = 7.5,
        timeframe = "1m",
        rules = ["rsi_cross","vol_spike"]
    )
    await _queue.put(s.json())
