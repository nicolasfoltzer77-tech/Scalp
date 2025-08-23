# bot.py
from __future__ import annotations
import asyncio
import os
import sys, subprocess

def ensure_ccxt():
    try:
        import ccxt  # noqa
    except ImportError:
        print("[i] ccxt non installé, tentative d'installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ccxt>=4.0.0"])
        import ccxt  # noqa

ensure_ccxt()

os.environ["BT_DEBUG"] = "1"

from scalper.config import load_settings          # ✅ maintenant import direct
from scalper.live.orchestrator import run_orchestrator
from scalper.live.notify import build_notifier_and_stream

# >>>> TODO: remplace DummyExchange par ton client Bitget/CCXT asynchrone
class DummyExchange:
    async def fetch_ohlcv(self, symbol, timeframe="5m", limit=150):
        raise NotImplementedError("Brancher fetch_ohlcv sur ta source historique/CCXT.")
    async def create_order(self, symbol, type, side, qty):
        return {"id": "dummy", "status": "filled", "side": side, "qty": qty}

async def main():
    # Charge config (runtime) + secrets (.env)
    config, secrets = load_settings()

    # TODO: branche ici ton vrai exchange Bitget avec secrets
    # Exemple si tu utilises CCXT (asynchrone) :
    # import ccxt.async_support as ccxt
    # exchange = ccxt.bitget({
    #     "apiKey": secrets["BITGET_API_KEY"],
    #     "secret": secrets["BITGET_API_SECRET"],
    #     "password": secrets["BITGET_API_PASSWORD"],
    # })
    exchange = DummyExchange()

    notifier, command_stream = await build_notifier_and_stream()
    await run_orchestrator(
        exchange,
        config,
        symbols=config.get("top_symbols", []),
        notifier=notifier,
        command_stream=command_stream,
    )

if __name__ == "__main__":
    asyncio.run(main())
    