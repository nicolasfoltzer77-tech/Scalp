# bot.py
from __future__ import annotations
import asyncio

from scalp.config.loader import load_settings
from scalp.live.orchestrator import run_orchestrator
from scalp.live.notify import build_notifier_and_stream

# >>>> TODO: remplace DummyExchange par ton client Bitget/CCXT asynchrone
class DummyExchange:
    async def fetch_ohlcv(self, symbol, timeframe="5m", limit=150):
        raise NotImplementedError("Brancher fetch_ohlcv sur ta source historique/CCXT.")
    async def create_order(self, symbol, type, side, qty):
        return {"id": "dummy", "status": "filled", "side": side, "qty": qty}

async def main():
    config, secrets = load_settings()  # config = runtime (stratégie), secrets = .env
    # tu peux utiliser 'secrets' ici pour initialiser ton exchange réel
    exchange = DummyExchange()  # TODO: instancie ton vrai client Bitget avec secrets

    notifier, command_stream = await build_notifier_and_stream()
    await run_orchestrator(exchange, config, symbols=config.get("top_symbols", []),
                           notifier=notifier, command_stream=command_stream)

if __name__ == "__main__":
    asyncio.run(main())