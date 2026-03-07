from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.strategy_stability_analysis")


def _rolling_profit_factor(series: pd.Series, window: int) -> pd.Series:
    vals = []
    for i in range(len(series)):
        sub = series.iloc[max(0, i - window + 1): i + 1]
        profits = sub[sub > 0].sum()
        losses = sub[sub < 0].sum()
        if losses == 0:
            vals.append(np.nan if profits == 0 else np.inf)
        else:
            vals.append(profits / abs(losses))
    return pd.Series(vals, index=series.index)


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
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce").fillna(0.0)
    if work.empty:
        reason = "no rows"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    window = min(50, max(10, len(work) // 5))
    work["rolling_profit_factor"] = _rolling_profit_factor(work["pnl"], window)
    work["rolling_expectancy"] = work["pnl"].rolling(window, min_periods=max(5, window // 3)).mean()
    work["edge_decay"] = work["pnl"].expanding(min_periods=5).mean()

    sns.set_theme(style="whitegrid")

    for col in ["rolling_profit_factor", "rolling_expectancy", "edge_decay"]:
        plt.figure(figsize=(10, 4))
        plt.plot(work.index, work[col])
        plt.title(col.replace("_", " ").title())
        plt.tight_layout()
        plt.savefig(out["charts"] / f"{col}.png")
        plt.close()

    work[["pnl", "rolling_profit_factor", "rolling_expectancy", "edge_decay"]].to_csv(
        out["csv"] / "strategy_stability_analysis.csv", index=False
    )
    return {"status": "ok", "rows": int(len(work)), "table": table}
