from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

from analysis import db


ATR_LABELS = ["low", "medium", "high"]


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    atr_col = db.pick_first(trades.columns, ["atr_signal", "atr"])
    pnl_col = db.find_pnl_col(trades.columns)
    if not atr_col or not pnl_col:
        return {"status": "skipped", "reason": "missing atr_signal or pnl", "table": table}

    work = trades[[atr_col, pnl_col]].copy()
    work.columns = ["atr_signal", "pnl_net"]
    work = work.apply(pd.to_numeric, errors="coerce").dropna()
    if work.empty:
        return {"status": "skipped", "reason": "no valid atr rows", "table": table}

    try:
        work["atr_bucket"] = pd.qcut(work["atr_signal"], q=3, labels=ATR_LABELS)
    except ValueError:
        work["atr_bucket"] = pd.cut(work["atr_signal"], bins=3, labels=ATR_LABELS)

    metrics = db.compute_basic_metrics(work, "pnl_net", ["atr_bucket"])
    metrics["atr_bucket"] = pd.Categorical(metrics["atr_bucket"], categories=ATR_LABELS, ordered=True)
    metrics = metrics.sort_values("atr_bucket")
    metrics.to_csv(out["csv"] / "atr_expectancy_metrics.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.bar(metrics["atr_bucket"].astype(str), metrics["expectancy"], color="tab:blue")
    plt.title("Expectancy vs ATR Bucket")
    plt.xlabel("ATR bucket")
    plt.ylabel("expectancy")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_atr.png")
    plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table}
