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
        reason = "trades table not found"
        log.warning(reason)
        return {"status": "skipped", "reason": reason}

    pnl_col = db.find_pnl_col(trades.columns)
    tcol = db.pick_first(trades.columns, ["close_time", "ts_close", "open_time", "ts_open", "ts"])
    if pnl_col is None or tcol is None:
        reason = "missing pnl/time columns"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    work["t"] = db.to_datetime_series(work[tcol])
    work = work.dropna(subset=["t", "pnl"])
    if work.empty:
        reason = "no valid rows after time conversion"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    work["hour"] = work["t"].dt.hour
    work["weekday"] = work["t"].dt.day_name()

    sns.set_theme(style="whitegrid")

    by_hour = work.groupby("hour", observed=False)["pnl"].sum().reset_index(name="pnl_sum")
    plt.figure(figsize=(8, 4))
    sns.barplot(data=by_hour, x="hour", y="pnl_sum")
    plt.title("PnL by Hour")
    plt.tight_layout()
    plt.savefig(out["charts"] / "pnl_by_hour.png")
    plt.close()

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_weekday = work.groupby("weekday", observed=False)["pnl"].sum().reindex(order).reset_index(name="pnl_sum")
    plt.figure(figsize=(9, 4))
    sns.barplot(data=by_weekday, x="weekday", y="pnl_sum")
    plt.title("PnL by Weekday")
    plt.xticks(rotation=25)
    plt.tight_layout()
    plt.savefig(out["charts"] / "pnl_by_weekday.png")
    plt.close()

    expectancy = work.groupby("hour", observed=False)["pnl"].mean().reset_index(name="expectancy")
    plt.figure(figsize=(8, 4))
    sns.lineplot(data=expectancy, x="hour", y="expectancy", marker="o")
    plt.title("Expectancy by Hour")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_by_hour.png")
    plt.close()

    work[["t", "hour", "weekday", "pnl"]].to_csv(out["csv"] / "time_analysis_extended.csv", index=False)
    return {"status": "ok", "rows": int(len(work)), "table": table}
