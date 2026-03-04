from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
except Exception:
    KMeans = None
    StandardScaler = None

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    if KMeans is None or StandardScaler is None:
        return {"status": "skipped", "reason": "scikit-learn not installed"}

    trades, trade_table = db.load_first_table(conn, ["recorder_trades", "recorder"])
    steps, step_table = db.load_first_table(conn, ["recorder_steps"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    tid_t = db.find_trade_id_col(trades.columns)
    pnl_col = db.find_pnl_col(trades.columns)
    symbol_col = db.find_symbol_col(trades.columns)
    lev_col = db.find_leverage_col(trades.columns)
    step_col = db.find_step_col(trades.columns)
    oc, cc = db.find_open_close_time_cols(trades.columns)

    required = [tid_t, pnl_col, symbol_col, lev_col, step_col]
    if any(c is None for c in required):
        return {"status": "skipped", "reason": "missing required clustering columns", "table": trade_table}

    df = trades.copy()
    if steps is not None:
        tid_s = db.find_trade_id_col(steps.columns)
        if tid_s and "exec_type" in steps.columns:
            pyr_count = (
                steps[steps["exec_type"].astype(str).str.lower() == "pyramide"]
                .groupby(tid_s)
                .size()
                .reset_index(name="pyramide_count")
                .rename(columns={tid_s: tid_t})
            )
            df = df.merge(pyr_count, on=tid_t, how="left")

    df["pyramide_count"] = df.get("pyramide_count", 0).fillna(0)
    if oc and cc:
        df["duration"] = (db.to_datetime_series(df[cc]) - db.to_datetime_series(df[oc])).dt.total_seconds()
    else:
        df["duration"] = 0

    df["symbol_encoded"] = df[symbol_col].astype("category").cat.codes
    features = [lev_col, step_col, "duration", "pyramide_count", "symbol_encoded", pnl_col]
    x = df[features].apply(pd.to_numeric, errors="coerce").dropna()
    if len(x) < 10:
        return {"status": "skipped", "reason": "not enough rows for clustering", "table": trade_table}

    x_scaled = StandardScaler().fit_transform(x)
    km = KMeans(n_clusters=5, random_state=42, n_init=20)
    clusters = km.fit_predict(x_scaled)

    clustered = df.loc[x.index].copy()
    clustered["cluster"] = clusters
    clustered.to_csv(out["csv"] / "trade_clusters_advanced.csv", index=False)

    summary = db.compute_basic_metrics(clustered, pnl_col, ["cluster"])
    summary = summary.rename(columns={"trades": "trade_count"}).sort_values("expectancy", ascending=False)
    summary.to_csv(out["csv"] / "cluster_summary.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.bar(summary["cluster"].astype(str), summary["expectancy"], color="tab:cyan")
    plt.title("Cluster Expectancy")
    plt.xlabel("Cluster")
    plt.ylabel("Expectancy")
    plt.tight_layout()
    plt.savefig(out["charts"] / "cluster_expectancy.png")
    plt.close()

    return {"status": "ok", "rows": len(clustered), "trade_table": trade_table, "step_table": step_table}
