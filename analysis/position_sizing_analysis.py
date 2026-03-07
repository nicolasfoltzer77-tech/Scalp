from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.position_sizing_analysis")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    size_col = db.pick_first(trades.columns, ["size", "position_size", "qty", "quantity", "contracts"])
    lev_col = db.find_leverage_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    if size_col:
        work["size"] = pd.to_numeric(work[size_col], errors="coerce")
    else:
        work["size"] = pd.NA
        log.warning("Missing size column; sizing charts requiring size will be skipped")

    if lev_col:
        work["leverage"] = pd.to_numeric(work[lev_col], errors="coerce")
    else:
        work["leverage"] = pd.NA
        log.warning("Missing leverage column; leverage chart will be skipped")

    sns.set_theme(style="whitegrid")

    s = work[["size", "pnl"]].dropna()
    if s.empty:
        log.warning("Skipping size_vs_pnl and expectancy_vs_size_bucket: missing size data")
    else:
        plt.figure(figsize=(8, 4.8))
        sns.scatterplot(data=s, x="size", y="pnl", alpha=0.35)
        plt.title("Size vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "size_vs_pnl.png")
        plt.close()

        s["size_bucket"] = pd.qcut(s["size"], q=min(8, s["size"].nunique()), duplicates="drop")
        e = s.groupby("size_bucket", observed=False)["pnl"].mean().reset_index(name="expectancy")
        plt.figure(figsize=(9, 4.8))
        plt.plot(range(len(e)), e["expectancy"].values, marker="o")
        plt.xticks(range(len(e)), e["size_bucket"].astype(str), rotation=45, ha="right")
        plt.title("Expectancy vs Size Bucket")
        plt.tight_layout()
        plt.savefig(out["charts"] / "expectancy_vs_size_bucket.png")
        plt.close()

    l = work[["leverage", "pnl"]].dropna()
    if l.empty:
        log.warning("Skipping leverage_vs_pnl: missing leverage data")
    else:
        plt.figure(figsize=(8, 4.8))
        sns.scatterplot(data=l, x="leverage", y="pnl", alpha=0.35)
        plt.title("Leverage vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "leverage_vs_pnl.png")
        plt.close()

    return {"status": "ok", "rows": int(work["pnl"].notna().sum()), "table": table}
