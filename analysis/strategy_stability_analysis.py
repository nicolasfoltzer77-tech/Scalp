from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.strategy_stability_analysis")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    work = work.dropna(subset=["pnl"]).reset_index(drop=True)
    if work.empty:
        return {"status": "skipped", "reason": "no numeric pnl rows", "table": table}

    window = max(20, min(100, len(work) // 5 if len(work) > 50 else 20))
    roll = work["pnl"].rolling(window)
    gains = work["pnl"].clip(lower=0).rolling(window).sum()
    losses = work["pnl"].clip(upper=0).rolling(window).sum().abs().replace(0, np.nan)
    work["rolling_profit_factor"] = gains / losses
    work["rolling_expectancy"] = roll.mean()

    baseline = work["pnl"].iloc[:window].mean() if len(work) >= window else work["pnl"].mean()
    work["edge_decay"] = work["rolling_expectancy"] - baseline

    sns.set_theme(style="whitegrid")

    for col, fname, title in [
        ("rolling_profit_factor", "rolling_profit_factor.png", "Rolling Profit Factor"),
        ("rolling_expectancy", "rolling_expectancy_stability.png", "Rolling Expectancy (Stability)"),
        ("edge_decay", "edge_decay.png", "Edge Decay"),
    ]:
        vals = work[col].dropna()
        if vals.empty:
            log.warning("Skipping %s: insufficient rows for rolling window=%s", fname, window)
            continue
        plt.figure(figsize=(10, 4.8))
        plt.plot(vals.values, linewidth=1.7)
        plt.title(title)
        plt.xlabel("Trades")
        plt.tight_layout()
        plt.savefig(out["charts"] / fname)
        plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table, "rolling_window": window}
