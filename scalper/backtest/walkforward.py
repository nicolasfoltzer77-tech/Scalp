from __future__ import annotations

from itertools import product
from statistics import mean, stdev
from typing import Dict, Iterable, Optional

from ..strategy import max_drawdown


def _sharpe(returns: Iterable[float]) -> float:
    vals = list(returns)
    if not vals:
        return 0.0
    mu = mean(vals)
    if len(vals) > 1:
        sd = stdev(vals)
    else:
        sd = 0.0
    return mu / sd if sd > 0 else 0.0


def _stability(equity: Iterable[float]) -> float:
    curve = list(equity)
    n = len(curve)
    if n < 2:
        return 0.0
    x = list(range(n))
    x_mean = sum(x) / n
    y_mean = sum(curve) / n
    ss_tot = sum((y - y_mean) ** 2 for y in curve)
    denom = sum((xi - x_mean) ** 2 for xi in x)
    if denom == 0 or ss_tot == 0:
        return 0.0
    b = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, curve)) / denom
    a = y_mean - b * x_mean
    ss_res = sum((yi - (a + b * xi)) ** 2 for xi, yi in zip(x, curve))
    return 1 - ss_res / ss_tot


def walk_forward(
    df,
    splits: int = 5,
    train_ratio: float = 0.7,
    params: Optional[Dict[str, Iterable]] = None,
) -> Dict[str, float]:
    """Perform walk-forward optimisation and evaluation.

    Parameters
    ----------
    df:
        DataFrame containing per-period percentage returns. The first column is
        used when a dedicated ``"returns"`` column is not found.
    splits:
        Number of walk-forward test windows.
    train_ratio:
        Proportion of the data used for training in the initial window.
    params:
        Optional parameter grid. If provided, columns in ``df`` matching each
        parameter combination are evaluated and the best Sharpe ratio on the
        training window is selected. When ``None``, the first column is used.
    """

    if df.empty:
        return {"sharpe": 0.0, "mdd": 0.0, "pnl": 0.0, "stability": 0.0}

    returns_col = "returns" if "returns" in df.columns else df.columns[0]
    data = df.copy()

    n = len(data)
    train_len = max(1, int(n * train_ratio))
    test_len = max(1, (n - train_len) // splits) if splits else max(1, n - train_len)

    sharpe_list = []
    mdd_list = []
    pnl_list = []
    stability_list = []

    from . import walk_forward_windows

    indices = list(range(n))

    for tr_idx, te_idx in walk_forward_windows(indices, train_len, test_len):
        train_df = data.iloc[tr_idx]
        test_df = data.iloc[te_idx]

        # Parameter optimisation based on Sharpe ratio
        if params:
            best_col = None
            best_score = float("-inf")
            keys, values = zip(*params.items()) if params else ([], [])
            for combo in product(*values):
                col_name = "_".join(f"{k}={v}" for k, v in zip(keys, combo))
                if col_name not in data.columns:
                    continue
                score = _sharpe(train_df[col_name])
                if score > best_score:
                    best_score = score
                    best_col = col_name
            series = test_df[best_col] if best_col else test_df[returns_col]
        else:
            series = test_df[returns_col]

        sharpe_list.append(_sharpe(series))
        equity = (1 + series / 100.0).cumprod()
        mdd_list.append(max_drawdown(equity))
        pnl_list.append((equity.iloc[-1] - 1) * 100 if len(equity) else 0.0)
        stability_list.append(_stability(equity))

    count = len(sharpe_list) or 1
    mean_sharpe = sum(sharpe_list) / count
    mean_mdd = sum(mdd_list) / count
    mean_pnl = sum(pnl_list) / count
    mean_stability = sum(stability_list) / count

    return {
        "sharpe": mean_sharpe,
        "mdd": mean_mdd,
        "pnl": mean_pnl,
        "stability": mean_stability,
    }
