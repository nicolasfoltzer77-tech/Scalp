#!/usr/bin/env python3
from __future__ import annotations

from scalp.adapters.bitget import BitgetFuturesClient
from scalp.services.order_service import OrderService, OrderCaps, OrderRequest
from scalp.strategy import generate_signal, Signal
from scalp.config import load_or_exit

CONFIG = load_or_exit()


def process_signal(symbol: str, ohlcv_window, exchange: BitgetFuturesClient, order_service: OrderService):
    sig = generate_signal(symbol=symbol, ohlcv=ohlcv_window, config=CONFIG)
    if sig:
        assets = exchange.get_assets()
        equity_usdt = next((a["equity"] for a in assets["data"] if a.get("currency") == "USDT"), 0.0)
        req = OrderRequest(
            symbol=sig.symbol,
            side="long" if sig.side > 0 else "short",
            price=sig.entry,
            sl=sig.sl,
            tp=sig.tp1 or sig.tp2,
            risk_pct=CONFIG.RISK_PCT,
        )
        return order_service.prepare_and_place(equity_usdt, req)
    return None


def main():
    exchange = BitgetFuturesClient(
        api_key=CONFIG.BITGET_API_KEY,
        secret=CONFIG.BITGET_API_SECRET,
        passphrase=CONFIG.BITGET_PASSPHRASE,
        paper_trade=CONFIG.PAPER_TRADE,
    )
    order_service = OrderService(
        exchange, OrderCaps(min_trade_usdt=CONFIG.MIN_TRADE_USDT, leverage=CONFIG.LEVERAGE)
    )
    # Orchestration logic goes here
    pass


if __name__ == "__main__":
    main()
