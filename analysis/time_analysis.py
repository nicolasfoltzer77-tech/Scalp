from __future__ import annotations

import pandas as pd
import sqlite3

from . import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    pnl_col = db.find_pnl_col(trades.columns)
    oc, cc = db.find_open_close_time_cols(trades.columns)
    if not pnl_col or not oc or not cc:
        return {"status": "skipped", "reason": "missing pnl or open/close timestamps"}

    duration = (db.to_datetime_series(trades[cc]) - db.to_datetime_series(trades[oc])).dt.total_seconds()
    trades["duration_s"] = duration
    bins = [0, 30, 60, 180, 600, float("inf")]
    labels = ["0-30 sec", "30-60 sec", "1-3 min", "3-10 min", "10+ min"]
    trades["duration_bucket"] = pd.cut(duration, bins=bins, labels=labels, right=False)

    metrics = db.compute_basic_metrics(trades, pnl_col, ["duration_bucket"])
    metrics.to_csv(out["csv"] / "time_duration_metrics.csv", index=False)
    return {"status": "ok", "rows": len(metrics)}
