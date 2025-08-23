import asyncio

from scalper.ws import WebsocketManager


def test_websocket_manager_stop():
    async def connect():
        return None

    async def subscribe():
        return None

    ws = WebsocketManager(connect, subscribe, heartbeat_interval=0.01)

    async def run_and_stop():
        await ws.run()
        assert ws._heartbeat_task is not None
        await ws.stop()
        assert ws._heartbeat_task is None

    asyncio.run(run_and_stop())
