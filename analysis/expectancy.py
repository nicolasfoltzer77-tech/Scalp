from __future__ import annotations

import sqlite3
import pandas as pd

from . import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column"}

    oc, cc = db.find_open_close_time_cols(trades.columns)
    if oc:
        dt = db.to_datetime_series(trades[oc])
        trades["hour_of_day"] = dt.dt.hour
        trades["day_of_week"] = dt.dt.day_name()

    lev_col = db.find_leverage_col(trades.columns)
    if lev_col:
        trades["leverage_bucket"] = db.leverage_bucket(trades[lev_col])

    groups = {
        "symbol": db.find_symbol_col(trades.columns),
        "dec_mode": db.find_dec_mode_col(trades.columns),
        "leverage_bucket": "leverage_bucket" if "leverage_bucket" in trades.columns else None,
        "step": db.find_step_col(trades.columns),
        "hour_of_day": "hour_of_day" if "hour_of_day" in trades.columns else None,
        "day_of_week": "day_of_week" if "day_of_week" in trades.columns else None,
    }

    for name, col in groups.items():
        if not col:
            continue
        metrics = db.compute_basic_metrics(trades, pnl_col, [col]).sort_values("expectancy", ascending=False)
        metrics.to_csv(out["csv"] / f"expectancy_by_{name}.csv", index=False)

    return {"status": "ok", "rows": len(trades)}
