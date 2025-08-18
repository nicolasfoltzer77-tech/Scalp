from scalp.opt import run_parallel


def square(x: int) -> int:
    return x * x


def test_run_parallel_returns_n_results():
    data = [1, 2, 3]
    result = run_parallel(square, data, processes=2)
    assert result == [1, 4, 9]
    assert len(result) == len(data)
