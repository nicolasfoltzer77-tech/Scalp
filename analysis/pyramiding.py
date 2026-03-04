from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
try:
    import seaborn as sns
except Exception:  # optional plotting dependency
    sns = None
import sqlite3

from . import db


def _bucket(n: float) -> str:
    if pd.isna(n):
        return "0"
    n = int(n)
    return "5+" if n >= 5 else str(n)


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    steps = db.load_table(conn, "recorder_steps")

    tid_t = db.find_trade_id_col(trades.columns)
    tid_s = db.find_trade_id_col(steps.columns)
    pnl_col = db.find_pnl_col(trades.columns)
    if not tid_t or not tid_s or not pnl_col or "exec_type" not in steps.columns:
        return {"status": "skipped", "reason": "missing required columns"}

    pyr = (steps[steps["exec_type"].astype(str).str.lower() == "pyramide"]
           .groupby(tid_s).size().reset_index(name="pyramide_count"))
    merged = trades.merge(pyr, left_on=tid_t, right_on=tid_s, how="left")
    merged["pyramide_count"] = merged["pyramide_count"].fillna(0)

    oc, cc = db.find_open_close_time_cols(merged.columns)
    if oc and cc:
        merged["duration_seconds"] = (db.to_datetime_series(merged[cc]) - db.to_datetime_series(merged[oc])).dt.total_seconds()

    merged["pyramide_bucket"] = merged["pyramide_count"].map(_bucket)
    metrics = db.compute_basic_metrics(merged, pnl_col, ["pyramide_bucket"])
    metrics.to_csv(out["csv"] / "pyramiding_expectancy.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")
    plt.figure(figsize=(8, 4))
    order = ["0", "1", "2", "3", "4", "5+"]
    if sns:
        sns.barplot(data=metrics, x="pyramide_bucket", y="expectancy", order=order)
    else:
        fallback = metrics.set_index("pyramide_bucket").reindex(order).fillna(0)
        plt.bar(fallback.index.astype(str), fallback["expectancy"])
    plt.title("Expectancy vs pyramiding count")
    plt.tight_layout()
    plt.savefig(out["charts"] / "pyramiding_expectancy.png")
    plt.close()

    return {"status": "ok", "rows": len(merged)}
