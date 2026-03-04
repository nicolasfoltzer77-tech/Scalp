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


def _compute_entry_efficiency(df: pd.DataFrame, side_col: str, entry_col: str, mfe_col: str, mae_col: str) -> pd.Series:
    side = df[side_col].astype(str).str.upper()
    entry = pd.to_numeric(df[entry_col], errors="coerce")
    mfe_price = pd.to_numeric(df[mfe_col], errors="coerce")
    mae_price = pd.to_numeric(df[mae_col], errors="coerce")
    denom = (mfe_price - mae_price).replace(0, np.nan)

    long_eff = (entry - mae_price) / denom
    short_eff = (mfe_price - entry) / denom
    eff = np.where(side.str.contains("SHORT"), short_eff, long_eff)
    return pd.Series(eff, index=df.index).clip(lower=0, upper=1)


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
        return {"status": "skipped", "reason": "missing columns for entry efficiency", "table": table}

    work = trades.copy()
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    work["entry_efficiency"] = _compute_entry_efficiency(work, side_col, entry_col, mfe_col, mae_col)

    export_cols = [c for c in [uid_col, side_col, entry_col, mfe_col, mae_col, pnl_col] if c]
    work[export_cols + ["entry_efficiency"]].to_csv(out["csv"] / "entry_efficiency_metrics.csv", index=False)

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4))
    sns.histplot(work["entry_efficiency"].dropna(), bins=30, kde=True)
    plt.title("Entry Efficiency Distribution")
    plt.xlabel("entry_efficiency")
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_efficiency_hist.png")
    plt.close()

    plt.figure(figsize=(7, 5))
    sns.scatterplot(data=work, x="entry_efficiency", y=pnl_col, alpha=0.45)
    plt.title("Entry Efficiency vs PnL")
    plt.xlabel("entry_efficiency")
    plt.ylabel(pnl_col)
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_efficiency_vs_pnl.png")
    plt.close()

    return {"status": "ok", "rows": int(work[["entry_efficiency", pnl_col]].dropna().shape[0]), "table": table}
