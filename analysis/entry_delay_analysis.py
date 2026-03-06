from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

from analysis import db


DELAY_LABELS = ["0-1s", "1-5s", "5-10s", "10s+"]


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    open_col = db.pick_first(trades.columns, ["ts_open", "open_time", "ts_entry"])
    signal_col = db.pick_first(trades.columns, ["ts_signal", "signal_ts", "ts_sig", "signal_time"])
    if not pnl_col or not open_col or not signal_col:
        return {"status": "skipped", "reason": "missing ts_open/ts_signal/pnl columns", "table": table}

    work = trades[[open_col, signal_col, pnl_col]].copy()
    work.columns = ["ts_open", "ts_signal", "pnl_net"]
    work["pnl_net"] = pd.to_numeric(work["pnl_net"], errors="coerce")

    open_ts = db.to_datetime_series(work["ts_open"])
    signal_ts = db.to_datetime_series(work["ts_signal"])
    work["entry_delay_s"] = (open_ts - signal_ts).dt.total_seconds()
    work = work.dropna(subset=["entry_delay_s", "pnl_net"])
    work = work[work["entry_delay_s"] >= 0]
    if work.empty:
        return {"status": "skipped", "reason": "no valid delay rows", "table": table}

    bins = [0, 1, 5, 10, float("inf")]
    work["delay_bucket"] = pd.cut(work["entry_delay_s"], bins=bins, labels=DELAY_LABELS, right=False)

    metrics = db.compute_basic_metrics(work, "pnl_net", ["delay_bucket"])
    metrics["delay_bucket"] = pd.Categorical(metrics["delay_bucket"], categories=DELAY_LABELS, ordered=True)
    metrics = metrics.sort_values("delay_bucket")

    plt.figure(figsize=(8, 4.5))
    plt.bar(metrics["delay_bucket"].astype(str), metrics["expectancy"], color="tab:green")
    plt.title("Expectancy vs Entry Delay")
    plt.xlabel("delay bucket")
    plt.ylabel("expectancy")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_entry_delay.png")
    plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table}
