# bot.py
from __future__ import annotations
import asyncio, os

from scalp.live.orchestrator import run_orchestrator
from scalp.live.notify import build_notifier_and_stream

# >>>> Remplace par ton vrai exchange Bitget/CCXT (async)
class DummyExchange:
    async def fetch_ohlcv(self, symbol, timeframe="5m", limit=150):
        raise NotImplementedError("Brancher DummyExchange.fetch_ohlcv sur ta source (ou CCXT).")
    async def create_order(self, symbol, type, side, qty):
        return {"id": "dummy", "status": "filled", "side": side, "qty": qty}

async def main():
    exchange = DummyExchange()  # TODO: instancier ton vrai client
    config = {
        "timeframe": os.getenv("TIMEFRAME", "5m"),
        "cash": float(os.getenv("CASH", "10000")),
    }
    notifier, command_stream = await build_notifier_and_stream()
    await run_orchestrator(exchange, config, symbols=[], notifier=notifier, command_stream=command_stream)

if __name__ == "__main__":
    asyncio.run(main())