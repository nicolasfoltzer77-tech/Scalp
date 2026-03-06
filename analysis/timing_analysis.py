from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    open_col = db.pick_first(trades.columns, ["ts_open", "open_time", "ts_entry"])
    mfe_ts_col = db.pick_first(trades.columns, ["mfe_ts"])
    mae_ts_col = db.pick_first(trades.columns, ["mae_ts"])
    if not pnl_col or not open_col or not mfe_ts_col or not mae_ts_col:
        return {"status": "skipped", "reason": "missing timing columns", "table": table}

    work = trades[[open_col, mfe_ts_col, mae_ts_col, pnl_col]].copy()
    work.columns = ["ts_open", "mfe_ts", "mae_ts", "pnl_net"]
    work["pnl_net"] = pd.to_numeric(work["pnl_net"], errors="coerce")

    open_ts = db.to_datetime_series(work["ts_open"])
    mfe_ts = db.to_datetime_series(work["mfe_ts"])
    mae_ts = db.to_datetime_series(work["mae_ts"])
    work["time_to_mfe"] = (mfe_ts - open_ts).dt.total_seconds()
    work["time_to_mae"] = (mae_ts - open_ts).dt.total_seconds()

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4.5))
    sns.histplot(work["time_to_mfe"].dropna(), bins=40, kde=True)
    plt.title("Time to MFE Distribution (seconds)")
    plt.xlabel("time_to_mfe (s)")
    plt.tight_layout()
    plt.savefig(out["charts"] / "time_to_mfe_distribution.png")
    plt.close()

    plt.figure(figsize=(8, 4.5))
    sns.histplot(work["time_to_mae"].dropna(), bins=40, kde=True, color="tab:red")
    plt.title("Time to MAE Distribution (seconds)")
    plt.xlabel("time_to_mae (s)")
    plt.tight_layout()
    plt.savefig(out["charts"] / "time_to_mae_distribution.png")
    plt.close()

    scatter = work[["time_to_mfe", "pnl_net"]].dropna()
    plt.figure(figsize=(7, 5))
    sns.scatterplot(data=scatter, x="time_to_mfe", y="pnl_net", alpha=0.45)
    plt.title("Time to MFE vs PnL")
    plt.xlabel("time_to_mfe (s)")
    plt.ylabel("pnl_net")
    plt.tight_layout()
    plt.savefig(out["charts"] / "time_to_mfe_vs_pnl.png")
    plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table}
