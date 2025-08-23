import pytest

from scalp import strategy
from scalper.trade_utils import trailing_stop, should_scale_in, timeout_exit


def make_ohlcv(n=60, start=100, step=1):
    closes = [start + i * step for i in range(n)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [1 for _ in closes]
    return {"open": closes, "high": highs, "low": lows, "close": closes, "volume": vols}


def test_generate_signal_atr_adaptation(monkeypatch):
    base = make_ohlcv(step=2)
    ohlcv_15 = make_ohlcv(n=15, step=2)
    ohlcv_1h = make_ohlcv(step=2)

    # patches for deterministic RSI values
    rsi_vals = iter([60, 41, 39])
    monkeypatch.setattr(strategy, "calc_rsi", lambda *args, **kwargs: next(rsi_vals))
    monkeypatch.setattr(strategy, "calc_position_size", lambda equity, risk, dist: 100)
    # low ATR -> signal disabled
    monkeypatch.setattr(strategy, "calc_atr", lambda *args, **kwargs: 0.1)
    sig = strategy.generate_signal(
        "AAA",
        base,
        equity=1_000,
        risk_pct=0.01,
        ohlcv_15m=ohlcv_15,
        ohlcv_1h=ohlcv_1h,
        order_book={"bid_vol_aggreg": 120, "ask_vol_aggreg": 80},
        tick_ratio_buy=0.6,
    )
    assert sig is None

    # high ATR -> size reduced
    rsi_vals = iter([60, 41, 39])
    monkeypatch.setattr(strategy, "calc_rsi", lambda *args, **kwargs: next(rsi_vals))
    monkeypatch.setattr(strategy, "calc_atr", lambda *args, **kwargs: 5.0)
    sig = strategy.generate_signal(
        "AAA",
        base,
        equity=1_000,
        risk_pct=0.01,
        ohlcv_15m=ohlcv_15,
        ohlcv_1h=ohlcv_1h,
        order_book={"bid_vol_aggreg": 120, "ask_vol_aggreg": 80},
        tick_ratio_buy=0.6,
    )
    assert sig and sig.side == "long"
    assert sig.qty == 50


def test_generate_signal_short_with_filters(monkeypatch):
    base = make_ohlcv(start=200, step=-2)
    ohlcv_15 = make_ohlcv(n=15, start=200, step=-2)
    ohlcv_1h = make_ohlcv(start=200, step=-2)

    rsi_vals = iter([40, 59, 61])
    monkeypatch.setattr(strategy, "calc_rsi", lambda *args, **kwargs: next(rsi_vals))
    monkeypatch.setattr(strategy, "calc_position_size", lambda equity, risk, dist: 100)
    monkeypatch.setattr(strategy, "calc_atr", lambda *args, **kwargs: 1.0)

    sig = strategy.generate_signal(
        "AAA",
        base,
        equity=1_000,
        risk_pct=0.01,
        ohlcv_15m=ohlcv_15,
        ohlcv_1h=ohlcv_1h,
        order_book={"bid_vol_aggreg": 80, "ask_vol_aggreg": 120},
        tick_ratio_buy=0.4,
    )
    assert sig and sig.side == "short"
    assert sig.qty == 100


def test_trailing_and_timeout():
    # trailing stop
    sl = trailing_stop("long", current_price=110, atr=10, sl=90)
    assert sl == pytest.approx(102.5)
    # scaling
    assert should_scale_in(100, 105, 100, 10, "long") is True
    assert should_scale_in(100, 95, 100, 10, "short") is True
    # timeout
    # before the progress window no exit should be triggered
    assert not timeout_exit(0, 10 * 60, 100, 99, "long", progress_min=15, timeout_min=30)
    # after ``progress_min`` minutes without favourable movement we close
    assert timeout_exit(0, 20 * 60, 100, 99, "long", progress_min=15, timeout_min=30)


def test_generate_signal_macd_filter(monkeypatch):
    base = make_ohlcv(step=2)
    ohlcv_15 = make_ohlcv(n=15, step=2)
    ohlcv_1h = make_ohlcv(step=2)

    rsi_vals = iter([60, 41, 39])
    monkeypatch.setattr(strategy, "calc_rsi", lambda *args, **kwargs: next(rsi_vals))
    monkeypatch.setattr(strategy, "calc_position_size", lambda equity, risk, dist: 100)
    monkeypatch.setattr(strategy, "calc_atr", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(strategy, "calc_macd", lambda *args, **kwargs: (-1.0, 0.0, -1.0))

    sig = strategy.generate_signal(
        "AAA",
        base,
        equity=1_000,
        risk_pct=0.01,
        ohlcv_15m=ohlcv_15,
        ohlcv_1h=ohlcv_1h,
        order_book={"bid_vol_aggreg": 120, "ask_vol_aggreg": 80},
        tick_ratio_buy=0.6,
    )
    assert sig is None



def test_generate_signal_trend_ema_filter(monkeypatch):
    base = make_ohlcv(step=2)
    ohlcv_15 = make_ohlcv(n=15, step=2)
    ohlcv_1h = make_ohlcv(step=2)

    rsi_vals = iter([60, 41, 39])
    monkeypatch.setattr(strategy, "calc_rsi", lambda *args, **kwargs: next(rsi_vals))
    monkeypatch.setattr(strategy, "calc_position_size", lambda equity, risk, dist: 100)
    monkeypatch.setattr(strategy, "calc_atr", lambda *args, **kwargs: 1.0)

    orig_ema = strategy.ema

    def fake_ema(series, window):
        if window == 200:
            return [x + 1000 for x in orig_ema(series, window)]
        return orig_ema(series, window)

    monkeypatch.setattr(strategy, "ema", fake_ema)

    sig = strategy.generate_signal(
        "AAA",
        base,
        equity=1_000,
        risk_pct=0.01,
        ohlcv_15m=ohlcv_15,
        ohlcv_1h=ohlcv_1h,
        order_book={"bid_vol_aggreg": 120, "ask_vol_aggreg": 80},
        tick_ratio_buy=0.6,
        trend_ema_period=200,
    )
    assert sig is None
    