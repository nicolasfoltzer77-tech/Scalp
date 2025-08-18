from scalp.backtest import walk_forward_windows


def test_walk_forward_windows():
    data = list(range(10))
    windows = list(walk_forward_windows(data, train=4, test=2))
    assert windows == [
        ([0, 1, 2, 3], [4, 5]),
        ([2, 3, 4, 5], [6, 7]),
        ([4, 5, 6, 7], [8, 9]),
    ]
