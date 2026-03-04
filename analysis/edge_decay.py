from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
try:
    import seaborn as sns
except Exception:  # optional plotting dependency
    sns = None
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    steps = db.load_table(conn, "recorder_steps")
    tid_col = db.find_trade_id_col(steps.columns)
    pnl_col = db.find_pnl_col(steps.columns)
    ts_col = db.find_step_time_col(steps.columns)
    if not tid_col or not pnl_col or not ts_col:
        return {"status": "skipped", "reason": "missing step trade id/pnl/time"}

    steps["ts_dt"] = db.to_datetime_series(steps[ts_col])
    steps[pnl_col] = pd.to_numeric(steps[pnl_col], errors="coerce")
    steps = steps.sort_values([tid_col, "ts_dt"])

    entry = steps.groupby(tid_col)["ts_dt"].transform("min")
    steps["seconds_since_entry"] = (steps["ts_dt"] - entry).dt.total_seconds()
    steps["sec_bucket"] = (steps["seconds_since_entry"] // 10) * 10

    curve = steps.groupby("sec_bucket")[pnl_col].mean().reset_index(name="avg_pnl")
    curve.to_csv(out["csv"] / "edge_decay_curve.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 4))
    if sns:
        sns.lineplot(data=curve, x="sec_bucket", y="avg_pnl")
    else:
        plt.plot(curve["sec_bucket"], curve["avg_pnl"])
    plt.title("Edge decay: average pnl vs time since entry")
    plt.xlabel("Seconds since entry (bucketed, 10s)")
    plt.tight_layout()
    plt.savefig(out["charts"] / "edge_decay_curve.png")
    plt.close()

    return {"status": "ok", "rows": len(curve)}
