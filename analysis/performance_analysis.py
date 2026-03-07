from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.performance_analysis")


def _rolling_expectancy(series: pd.Series, window: int = 50) -> pd.Series:
    return series.rolling(window, min_periods=max(5, window // 5)).mean()


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        reason = "trades table not found"
        log.warning(reason)
        return {"status": "skipped", "reason": reason}

    pnl_col = db.find_pnl_col(trades.columns)
    if pnl_col is None:
        reason = "missing pnl column"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    work = trades.copy()
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    time_col = db.pick_first(work.columns, ["close_time", "ts_close", "open_time", "ts_open", "ts"])
    if time_col:
        work["_t"] = db.to_datetime_series(work[time_col])
        work = work.sort_values("_t")

    pnl = work[pnl_col].fillna(0.0)
    if pnl.empty:
        reason = "no pnl rows available"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    work["equity"] = pnl.cumsum()
    work["peak"] = work["equity"].cummax()
    work["drawdown"] = work["equity"] - work["peak"]
    work["win"] = (pnl > 0).astype(float)

    window = min(50, max(10, len(work) // 5))
    roll = pnl.rolling(window, min_periods=max(5, window // 3))
    work["rolling_sharpe"] = np.sqrt(window) * roll.mean() / roll.std(ddof=0).replace(0, np.nan)
    work["rolling_expectancy"] = _rolling_expectancy(pnl, window)
    work["rolling_winrate"] = work["win"].rolling(window, min_periods=max(5, window // 3)).mean()

    sns.set_theme(style="whitegrid")

    for col, title in [
        ("equity", "equity_curve"),
        ("drawdown", "drawdown_curve"),
        ("rolling_sharpe", "rolling_sharpe"),
        ("rolling_expectancy", "rolling_expectancy"),
        ("rolling_winrate", "rolling_winrate"),
    ]:
        plt.figure(figsize=(10, 4))
        plt.plot(work.index, work[col])
        plt.title(title.replace("_", " ").title())
        plt.tight_layout()
        plt.savefig(out["charts"] / f"{title}.png")
        plt.close()

    work[[pnl_col, "equity", "drawdown", "rolling_sharpe", "rolling_expectancy", "rolling_winrate"]].to_csv(
        out["csv"] / "performance_analysis.csv", index=False
    )
    return {"status": "ok", "rows": int(len(work)), "table": table}
