#!/usr/bin/env python3
"""Submit a simple market order on Bitget futures.

This helper reads API credentials and trade parameters from environment
variables (optionally loaded from a `.env` file) and places a one-way
market order.  Only the essential steps from the user's reference script
are kept to minimise latency and redundant code.

Environment variables:
    BITGET_API_KEY / BITGET_ACCESS_KEY
    BITGET_API_SECRET / BITGET_SECRET_KEY
    BITGET_API_PASSPHRASE
    BITGET_BASE_URL (default https://api.bitget.com)
    BITGET_PRODUCT_TYPE (default ``USDT-FUTURES``)
    BITGET_MARGIN_COIN (default ``USDT``)
    BITGET_SYMBOL (e.g. ``BTCUSDT``)
    BITGET_TEST_NOTIONAL_USDT (default ``5``)

Usage:
    python quick_order.py buy
    python quick_order.py sell
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from scalper.bitget_client import BitgetFuturesClient

# Load variables from `.env` if present
load_dotenv(Path(__file__).resolve().parent / ".env")

side = sys.argv[1].lower() if len(sys.argv) > 1 else "buy"
if side not in {"buy", "sell"}:
    raise SystemExit("Usage: quick_order.py [buy|sell]")

base = os.getenv("BITGET_BASE_URL", "https://api.bitget.com")
ak = os.getenv("BITGET_API_KEY") or os.getenv("BITGET_ACCESS_KEY")
sk = os.getenv("BITGET_API_SECRET") or os.getenv("BITGET_SECRET_KEY")
ph = os.getenv("BITGET_API_PASSPHRASE") or os.getenv("BITGET_PASSPHRASE")
product_type = os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES").upper()
margin_coin = os.getenv("BITGET_MARGIN_COIN", "USDT")
symbol = (os.getenv("BITGET_SYMBOL", "BTCUSDT") or "BTCUSDT").replace("_", "").upper()
notional = float(os.getenv("BITGET_TEST_NOTIONAL_USDT", "5"))

if not (ak and sk and ph):
    raise SystemExit("❌ BITGET_API_KEY/SECRET/PASSPHRASE manquants")

client = BitgetFuturesClient(
    access_key=ak,
    secret_key=sk,
    base_url=base,
    passphrase=ph,
    paper_trade=False,
)

tick = client.get_ticker(symbol)
price = None
try:
    data = tick.get("data")
    if isinstance(data, list) and data:
        price_str = data[0].get("lastPr") or data[0].get("lastPrice")
        if price_str is not None:
            price = float(price_str)
    elif isinstance(data, dict):
        price_str = data.get("lastPr") or data.get("lastPrice")
        if price_str is not None:
            price = float(price_str)
except Exception:
    pass
if price is None or price <= 0:
    raise SystemExit("Prix introuvable pour le ticker")

size = round(notional / price, 6)
client.set_position_mode_one_way(symbol, product_type)
client.set_leverage(symbol, product_type, margin_coin, leverage=2)
resp = client.place_market_order_one_way(
    symbol, side, size, product_type, margin_coin
)
print(resp)
