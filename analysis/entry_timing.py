from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sqlite3

from analysis import db


def _is_short(side: pd.Series) -> pd.Series:
    normalized = side.astype(str).str.upper()
    return normalized.str.contains("SHORT") | normalized.str.contains("SELL")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    side_col = db.find_side_col(trades.columns)
    entry_col = db.pick_first(trades.columns, ["entry", "entry_price", "price_open"])
    mfe_col = db.pick_first(trades.columns, ["mfe_price"])
    mae_col = db.pick_first(trades.columns, ["mae_price"])
    uid_col = db.find_trade_id_col(trades.columns)
    required = [pnl_col, side_col, entry_col, mfe_col, mae_col]
    if any(c is None for c in required):
        return {"status": "skipped", "reason": "missing columns for entry timing", "table": table}

    work = trades[[c for c in [uid_col, side_col, entry_col, mfe_col, mae_col, pnl_col] if c]].copy()
    for c in [entry_col, mfe_col, mae_col, pnl_col]:
        work[c] = pd.to_numeric(work[c], errors="coerce")

    denom = (work[mfe_col] - work[mae_col]).replace(0, np.nan)
    long_eff = (work[entry_col] - work[mae_col]) / denom
    short_eff = (work[mfe_col] - work[entry_col]) / denom
    work["entry_efficiency"] = np.where(_is_short(work[side_col]), short_eff, long_eff)

    csv_cols = [c for c in [uid_col, side_col, entry_col, mfe_col, mae_col, pnl_col] if c] + ["entry_efficiency"]
    work[csv_cols].to_csv(out["csv"] / "entry_efficiency_metrics.csv", index=False)

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4.5))
    sns.histplot(work["entry_efficiency"].dropna(), bins=40, kde=True)
    plt.title("Entry Efficiency Distribution")
    plt.xlabel("entry_efficiency")
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_efficiency_histogram.png")
    plt.close()

    scatter = work[["entry_efficiency", pnl_col]].dropna()
    plt.figure(figsize=(7, 5))
    sns.scatterplot(data=scatter, x="entry_efficiency", y=pnl_col, alpha=0.45)
    plt.title("Entry Efficiency vs PnL")
    plt.xlabel("entry_efficiency")
    plt.ylabel("pnl_net")
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_efficiency_vs_pnl.png")
    plt.close()

    return {"status": "ok", "rows": int(len(scatter)), "table": table}
