from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
try:
    import seaborn as sns
except Exception:  # optional plotting dependency
    sns = None
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    lev_col = db.find_leverage_col(trades.columns)
    pnl_col = db.find_pnl_col(trades.columns)
    if not lev_col or not pnl_col:
        return {"status": "skipped", "reason": "missing leverage or pnl column"}

    trades["leverage_bucket"] = db.leverage_bucket(trades[lev_col])
    metrics = db.compute_basic_metrics(trades, pnl_col, ["leverage_bucket"])
    metrics.to_csv(out["csv"] / "leverage_bucket_metrics.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")
    plt.figure(figsize=(8, 4))
    if sns:
        sns.barplot(data=metrics, x="leverage_bucket", y="expectancy")
    else:
        plt.bar(metrics["leverage_bucket"].astype(str), metrics["expectancy"])
    plt.title("Expectancy vs leverage bucket")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_leverage.png")
    plt.close()

    return {"status": "ok", "rows": len(metrics)}
