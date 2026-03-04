from __future__ import annotations

import pandas as pd
import sqlite3

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
except Exception:  # optional dependency
    KMeans = None
    StandardScaler = None

from . import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    if KMeans is None or StandardScaler is None:
        return {"status": "skipped", "reason": "scikit-learn not installed"}

    trades = db.load_table(conn, "recorder")
    steps = db.load_table(conn, "recorder_steps")

    tid_t = db.find_trade_id_col(trades.columns)
    tid_s = db.find_trade_id_col(steps.columns)
    pnl_col = db.find_pnl_col(trades.columns)
    symbol_col = db.find_symbol_col(trades.columns)
    lev_col = db.find_leverage_col(trades.columns)
    step_col = db.find_step_col(trades.columns)
    oc, cc = db.find_open_close_time_cols(trades.columns)
    if not all([tid_t, tid_s, pnl_col, symbol_col, lev_col, step_col]):
        return {"status": "skipped", "reason": "missing required clustering columns"}

    pyr_count = pd.DataFrame(columns=[tid_t, "pyramide_count"])
    if "exec_type" in steps.columns:
        pyr_count = (steps[steps["exec_type"].astype(str).str.lower() == "pyramide"]
                     .groupby(tid_s).size().reset_index(name="pyramide_count").rename(columns={tid_s: tid_t}))

    df = trades.merge(pyr_count, on=tid_t, how="left")
    df["pyramide_count"] = df["pyramide_count"].fillna(0)
    if oc and cc:
        df["duration_s"] = (db.to_datetime_series(df[cc]) - db.to_datetime_series(df[oc])).dt.total_seconds()
    else:
        df["duration_s"] = 0

    df["symbol_encoded"] = df[symbol_col].astype("category").cat.codes
    features = [lev_col, step_col, "duration_s", pnl_col, "pyramide_count", "symbol_encoded"]
    x = df[features].apply(pd.to_numeric, errors="coerce").dropna()
    if len(x) < 10:
        return {"status": "skipped", "reason": "not enough rows for clustering"}

    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)
    km = KMeans(n_clusters=5, random_state=42, n_init=20)
    clusters = km.fit_predict(x_scaled)

    clustered = df.loc[x.index].copy()
    clustered["cluster"] = clusters
    clustered.to_csv(out["csv"] / "trade_clusters.csv", index=False)

    summary = db.compute_basic_metrics(clustered, pnl_col, ["cluster"]).sort_values("expectancy", ascending=False)
    summary.to_csv(out["csv"] / "cluster_summary.csv", index=False)
    return {"status": "ok", "rows": len(clustered)}
