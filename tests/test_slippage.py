from scalp.trade_utils import marketable_limit_price


def test_marketable_limit_price_buy_sell():
    price_buy = marketable_limit_price("buy", best_bid=9.9, best_ask=10.0, slippage=0.001)
    assert price_buy == 10.0 * 1.001
    price_sell = marketable_limit_price("sell", best_bid=9.9, best_ask=10.0, slippage=0.001)
    assert price_sell == 9.9 * (1 - 0.001)
