from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

try:
    import seaborn as sns
except Exception:
    sns = None

from analysis import db


def _compute_entry_efficiency(df: pd.DataFrame, side_col: str, entry_col: str, low_col: str, high_col: str) -> pd.Series:
    side = df[side_col].astype(str).str.upper()
    entry = pd.to_numeric(df[entry_col], errors="coerce")
    low = pd.to_numeric(df[low_col], errors="coerce")
    high = pd.to_numeric(df[high_col], errors="coerce")
    denom = (high - low).replace(0, np.nan)

    long_eff = (entry - low) / denom
    short_eff = (high - entry) / denom
    eff = np.where(side.str.contains("SHORT"), short_eff, long_eff)
    return pd.Series(eff, index=df.index).clip(lower=0, upper=1)


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder_trades", "recorder"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    side_col = db.find_side_col(trades.columns)
    entry_col = db.find_price_col(trades.columns, "entry")
    low_col = db.find_price_col(trades.columns, "low")
    high_col = db.find_price_col(trades.columns, "high")
    tid_col = db.find_trade_id_col(trades.columns)

    required = [pnl_col, side_col, entry_col, low_col, high_col]
    if any(c is None for c in required):
        return {"status": "skipped", "reason": "missing columns for entry efficiency", "table": table}

    work = trades.copy()
    work["entry_efficiency"] = _compute_entry_efficiency(work, side_col, entry_col, low_col, high_col)
    metrics_cols = [c for c in [tid_col, side_col, entry_col, low_col, high_col, pnl_col] if c is not None]
    metrics = work[metrics_cols + ["entry_efficiency"]]
    metrics.to_csv(out["csv"] / "entry_efficiency_metrics.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4))
    if sns:
        sns.histplot(work["entry_efficiency"].dropna(), bins=30, kde=True)
    else:
        plt.hist(work["entry_efficiency"].dropna(), bins=30)
    plt.title("Entry Efficiency Distribution")
    plt.xlabel("entry_efficiency")
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_efficiency_histogram.png")
    plt.close()

    plt.figure(figsize=(7, 5))
    if sns:
        sns.scatterplot(data=work, x="entry_efficiency", y=pnl_col, alpha=0.45)
    else:
        plt.scatter(work["entry_efficiency"], work[pnl_col], alpha=0.45)
    plt.title("Entry Efficiency vs PnL")
    plt.xlabel("entry_efficiency")
    plt.ylabel(pnl_col)
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_efficiency_vs_pnl.png")
    plt.close()

    return {"status": "ok", "rows": len(metrics), "table": table}
