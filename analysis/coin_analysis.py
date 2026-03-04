from __future__ import annotations

import pandas as pd
import sqlite3

from . import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    symbol_col = db.find_symbol_col(trades.columns)
    pnl_col = db.find_pnl_col(trades.columns)
    oc, cc = db.find_open_close_time_cols(trades.columns)
    if not symbol_col or not pnl_col:
        return {"status": "skipped", "reason": "missing symbol or pnl"}

    if oc and cc:
        trades["duration_s"] = (db.to_datetime_series(trades[cc]) - db.to_datetime_series(trades[oc])).dt.total_seconds()

    metrics = db.compute_basic_metrics(trades, pnl_col, [symbol_col]).rename(columns={symbol_col: "symbol"})
    if "duration_s" in trades.columns:
        avg_dur = trades.groupby(symbol_col)["duration_s"].mean().reset_index(name="avg_duration_s")
        metrics = metrics.merge(avg_dur.rename(columns={symbol_col: "symbol"}), on="symbol", how="left")

    metrics.sort_values("expectancy", ascending=False).to_csv(out["csv"] / "coin_ranking.csv", index=False)
    metrics.nlargest(10, "expectancy").to_csv(out["csv"] / "best_coins.csv", index=False)
    metrics.nsmallest(10, "expectancy").to_csv(out["csv"] / "worst_coins.csv", index=False)
    return {"status": "ok", "rows": len(metrics)}
