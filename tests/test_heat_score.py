from scalp.pairs import heat_score, select_top_heat_pairs, decorrelate_pairs


def test_heat_score_value():
    assert heat_score(2.0, 100.0) == 200.0
    assert heat_score(2.0, 100.0, news=True) == 400.0


def test_select_and_decorrelate_pairs():
    pairs = [
        {"symbol": "A", "volatility": 2, "volume": 100, "news": True},
        {"symbol": "B", "volatility": 1, "volume": 200, "news": False},
        {"symbol": "C", "volatility": 1.5, "volume": 150, "news": False},
        {"symbol": "D", "volatility": 3, "volume": 50, "news": True},
    ]
    top = select_top_heat_pairs(pairs, top_n=3)
    assert len(top) == 3
    corr = {"A": {"B": 0.9}, "B": {"A": 0.9}, "C": {}, "D": {}}
    selected = decorrelate_pairs(pairs, corr, threshold=0.8, top_n=3)
    syms = {p["symbol"] for p in selected}
    assert not ("A" in syms and "B" in syms)
