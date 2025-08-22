#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService, OrderCaps
from scalp.config import load_or_exit
from live.orchestrator import run_orchestrator


def main():
    CONFIG = load_or_exit()
    parser = argparse.ArgumentParser()
    parser.add_argument("--async", dest="use_async", action="store_true", default=True, help="run with asyncio orchestrator (default)")
    parser.add_argument("--sync", dest="use_async", action="store_false", help="force legacy sync loop")
    parser.add_argument("--symbols", type=str, default="BTCUSDT,ETHUSDT", help="liste de symboles séparés par des virgules")
    args = parser.parse_args()

    exchange = BitgetFuturesClient(
        api_key=CONFIG.BITGET_API_KEY,
        secret=CONFIG.BITGET_API_SECRET,
        passphrase=CONFIG.BITGET_PASSPHRASE,
        paper_trade=CONFIG.PAPER_TRADE,
    )
    order_service = OrderService(exchange, OrderCaps(
        min_trade_usdt=getattr(CONFIG, "MIN_TRADE_USDT", 5.0),
        leverage=getattr(CONFIG, "LEVERAGE", 1.0),
    ))

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if args.use_async:
        asyncio.run(run_orchestrator(exchange, order_service, CONFIG, symbols))
        return

    # --------- CHEMIN LEGACY SYNC (EXISTANT) ---------
    # Conserver/laisser ton ancienne boucle ici pour compatibilité si besoin.
    # Sinon, on peut lever une exception claire:
    raise SystemExit("Legacy sync loop disabled; run without --sync or implement legacy path.")


if __name__ == "__main__":
    main()
