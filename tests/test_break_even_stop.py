from scalp.trade_utils import break_even_stop


def test_break_even_stop_long() -> None:
    sl = break_even_stop("long", entry_price=100, current_price=110, atr=5, sl=95)
    assert sl == 100
    sl = break_even_stop("long", entry_price=100, current_price=102, atr=5, sl=95)
    assert sl == 95


def test_break_even_stop_short() -> None:
    sl = break_even_stop("short", entry_price=100, current_price=90, atr=5, sl=105)
    assert sl == 100
    sl = break_even_stop("short", entry_price=100, current_price=97, atr=5, sl=105)
    assert sl == 105
