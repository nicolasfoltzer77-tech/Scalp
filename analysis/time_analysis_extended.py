from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.time_analysis_extended")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    _, close_col = db.find_open_close_time_cols(trades.columns)
    if not pnl_col or not close_col:
        return {"status": "skipped", "reason": "missing pnl or close timestamp", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    work["ts"] = db.to_datetime_series(work[close_col])
    work = work.dropna(subset=["pnl", "ts"])
    if work.empty:
        return {"status": "skipped", "reason": "no numeric pnl/timestamp rows", "table": table}

    work["hour"] = work["ts"].dt.hour
    work["weekday"] = work["ts"].dt.day_name()

    by_hour = work.groupby("hour", observed=False)["pnl"].sum().reset_index(name="pnl_sum")
    exp_hour = work.groupby("hour", observed=False)["pnl"].mean().reset_index(name="expectancy")
    by_weekday = work.groupby("weekday", observed=False)["pnl"].sum().reset_index(name="pnl_sum")
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_weekday["weekday"] = pd.Categorical(by_weekday["weekday"], categories=weekday_order, ordered=True)
    by_weekday = by_weekday.sort_values("weekday")

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(9, 4.8))
    sns.barplot(data=by_hour, x="hour", y="pnl_sum", color="#2563eb")
    plt.title("PnL by Hour")
    plt.tight_layout()
    plt.savefig(out["charts"] / "pnl_by_hour.png")
    plt.close()

    plt.figure(figsize=(10, 4.8))
    sns.barplot(data=by_weekday, x="weekday", y="pnl_sum", color="#0d9488")
    plt.title("PnL by Weekday")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(out["charts"] / "pnl_by_weekday.png")
    plt.close()

    plt.figure(figsize=(9, 4.8))
    sns.lineplot(data=exp_hour, x="hour", y="expectancy", marker="o")
    plt.title("Expectancy by Hour")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_by_hour.png")
    plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table}
