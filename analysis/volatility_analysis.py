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


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder_trades", "recorder"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    volatility_col = db.pick_first(trades.columns, ["volatility", "entry_volatility"])
    high_col = db.find_price_col(trades.columns, "high")
    low_col = db.find_price_col(trades.columns, "low")
    entry_col = db.find_price_col(trades.columns, "entry")

    if not pnl_col:
        return {"status": "skipped", "reason": "missing columns for volatility edge", "table": table}

    required_cols = [pnl_col]
    if volatility_col:
        required_cols.append(volatility_col)
    elif high_col and low_col and entry_col:
        required_cols.extend([high_col, low_col, entry_col])
    else:
        return {"status": "skipped", "reason": "missing volatility/high/low/entry columns", "table": table}

    work = trades[required_cols].copy()
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    if volatility_col:
        work["entry_volatility"] = pd.to_numeric(work[volatility_col], errors="coerce").abs()
    else:
        work[high_col] = pd.to_numeric(work[high_col], errors="coerce")
        work[low_col] = pd.to_numeric(work[low_col], errors="coerce")
        work[entry_col] = pd.to_numeric(work[entry_col], errors="coerce")
        work["entry_volatility"] = (work[high_col] - work[low_col]).abs() / work[entry_col].replace(0, np.nan).abs()
    work = work.dropna(subset=["entry_volatility", pnl_col])
    if work.empty:
        return {"status": "skipped", "reason": "no valid rows for volatility edge", "table": table}

    try:
        work["volatility_bucket"] = pd.qcut(work["entry_volatility"], q=3, labels=["low volatility", "medium volatility", "high volatility"])
    except ValueError:
        work["volatility_bucket"] = pd.cut(work["entry_volatility"], bins=3, labels=["low volatility", "medium volatility", "high volatility"])

    summary = db.compute_basic_metrics(work, pnl_col, ["volatility_bucket"]).sort_values("expectancy", ascending=False)
    summary.to_csv(out["csv"] / "volatility_expectancy.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.bar(summary["volatility_bucket"].astype(str), summary["expectancy"], color="tab:purple")
    plt.title("Expectancy vs Volatility Bucket")
    plt.xlabel("Volatility bucket")
    plt.ylabel("Expectancy")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_volatility.png")
    plt.close()

    return {"status": "ok", "rows": len(work), "table": table}
