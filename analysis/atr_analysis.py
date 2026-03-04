from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

from analysis import db


ATR_LABELS = ["low volatility", "medium volatility", "high volatility"]


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    atr_col = db.pick_first(trades.columns, ["atr_signal", "atr"])
    pnl_col = db.find_pnl_col(trades.columns)
    if not atr_col or not pnl_col:
        return {"status": "skipped", "reason": "missing atr or pnl column", "table": table}

    work = trades[[atr_col, pnl_col]].copy()
    work[atr_col] = pd.to_numeric(work[atr_col], errors="coerce")
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    work = work.dropna(subset=[atr_col, pnl_col])
    if work.empty:
        return {"status": "skipped", "reason": "no valid rows for atr analysis", "table": table}

    try:
        work["atr_bucket"] = pd.qcut(work[atr_col], q=3, labels=ATR_LABELS)
    except ValueError:
        work["atr_bucket"] = pd.cut(work[atr_col], bins=3, labels=ATR_LABELS)

    summary = db.compute_basic_metrics(work, pnl_col, ["atr_bucket"]) \
        .sort_values("atr_bucket", key=lambda s: s.astype(str).map({k: i for i, k in enumerate(ATR_LABELS)}))

    summary.to_csv(out["csv"] / "atr_expectancy.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.bar(summary["atr_bucket"].astype(str), summary["expectancy"], color="tab:blue")
    plt.title("Expectancy vs ATR Volatility Bucket")
    plt.xlabel("ATR bucket")
    plt.ylabel("Expectancy")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_atr.png")
    plt.close()

    return {"status": "ok", "rows": len(work), "table": table}
