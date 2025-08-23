# bot.py
from __future__ import annotations

import asyncio
import os
import sys
import subprocess

def ensure_ccxt() -> None:
    try:
        import ccxt  # noqa
    except ImportError:
        print("[i] ccxt non installé, tentative d'installation…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "ccxt"])

ensure_ccxt()

# Debug backtest optionnel
os.environ.setdefault("BT_DEBUG", "1")

from scalper.live.orchestrator import run_orchestrator
from scalper.live.notify import build_notifier_and_commands
from scalper.exchange.bitget_ccxt import create_exchange
# si tu as besoin de config: from scalper.config import load_settings

async def main():
    # notifier + flux de commandes (Telegram)
    notifier, command_stream = await build_notifier_and_commands()

    # exchange CCXT Bitget (public si pas de clés)
    exchange = await create_exchange()

    # symbols boot: laissé à l’orchestrateur (watchlist.get_boot_watchlist)
    symbols = []

    await run_orchestrator(
        exchange=exchange,
        config=None,
        symbols=symbols,
        notifier=notifier,
        command_stream=command_stream,
    )

if __name__ == "__main__":
    print("[*] Lancement du bot.py dans /scalp...")
    asyncio.run(main())