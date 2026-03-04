from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

from analysis import db


def _duration_seconds(open_s: pd.Series, close_s: pd.Series) -> pd.Series:
    open_num = pd.to_numeric(open_s, errors="coerce")
    close_num = pd.to_numeric(close_s, errors="coerce")
    numeric_usable = open_num.notna().mean() > 0.8 and close_num.notna().mean() > 0.8
    if numeric_usable:
        delta = close_num - open_num
        if delta.dropna().median() > 1e6:
            return delta / 1000.0
        return delta

    open_dt = db.to_datetime_series(open_s)
    close_dt = db.to_datetime_series(close_s)
    return (close_dt - open_dt).dt.total_seconds()


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    open_col, close_col = db.find_open_close_time_cols(trades.columns)
    if not pnl_col or not open_col or not close_col:
        return {"status": "skipped", "reason": "missing pnl/open/close columns", "table": table}

    work = trades[[open_col, close_col, pnl_col]].copy()
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    work["duration_seconds"] = _duration_seconds(work[open_col], work[close_col])
    work = work.dropna(subset=["duration_seconds", pnl_col])
    work = work[work["duration_seconds"] >= 0]
    if work.empty:
        return {"status": "skipped", "reason": "no valid durations", "table": table}

    work["duration_bucket"] = pd.cut(
        work["duration_seconds"],
        bins=[0, 30, 60, 180, 600, np.inf],
        labels=["0-30s", "30-60s", "1-3min", "3-10min", "10min+"],
        right=False,
    )

    summary = db.compute_basic_metrics(work.dropna(subset=["duration_bucket"]), pnl_col, ["duration_bucket"])
    order = {"0-30s": 0, "30-60s": 1, "1-3min": 2, "3-10min": 3, "10min+": 4}
    summary = summary.sort_values("duration_bucket", key=lambda s: s.astype(str).map(order))
    summary.to_csv(out["csv"] / "duration_expectancy.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.bar(summary["duration_bucket"].astype(str), summary["expectancy"], color="tab:red")
    plt.title("Expectancy vs Trade Duration")
    plt.xlabel("Duration bucket")
    plt.ylabel("Expectancy")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_duration.png")
    plt.close()

    return {"status": "ok", "rows": len(work), "table": table}
