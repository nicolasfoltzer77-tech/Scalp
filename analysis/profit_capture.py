from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    required_cols = {
        "entry": db.pick_first(trades.columns, ["entry", "entry_price", "price_open"]),
        "mfe_price": db.pick_first(trades.columns, ["mfe_price"]),
        "pnl": db.find_pnl_col(trades.columns),
    }
    if any(v is None for v in required_cols.values()):
        return {"status": "skipped", "reason": "missing columns for profit capture", "table": table}

    work = trades[[required_cols["entry"], required_cols["mfe_price"], required_cols["pnl"]]].copy()
    work.columns = ["entry", "mfe_price", "pnl_net"]
    work = work.apply(pd.to_numeric, errors="coerce")

    work["mfe"] = (work["mfe_price"] - work["entry"]).abs()
    work = work[(work["mfe_price"].notna()) & (work["mfe"] > 0)]
    if work.empty:
        return {"status": "skipped", "reason": "no valid rows after mfe filtering", "table": table}

    work["capture_ratio"] = work["pnl_net"] / work["mfe"]
    entry_abs = work["entry"].abs().replace(0, pd.NA)
    work["mfe_pct"] = (work["mfe"] / entry_abs) * 100
    work["realized_pnl_pct"] = (work["pnl_net"] / entry_abs) * 100

    metrics = pd.DataFrame(
        [
            {
                "metric": "average_capture_ratio",
                "value": float(work["capture_ratio"].mean()),
            },
            {
                "metric": "median_capture_ratio",
                "value": float(work["capture_ratio"].median()),
            },
            {
                "metric": "trades_used",
                "value": int(work["capture_ratio"].notna().sum()),
            },
        ]
    )
    metrics.to_csv(out["csv"] / "profit_capture_metrics.csv", index=False)

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4.5))
    sns.histplot(work["capture_ratio"].dropna(), bins=40, kde=True)
    plt.title("Profit Capture Ratio Distribution")
    plt.xlabel("capture_ratio = pnl_net / mfe")
    plt.tight_layout()
    plt.savefig(out["charts"] / "profit_capture_distribution.png")
    plt.close()

    scatter = work[["mfe_pct", "realized_pnl_pct"]].dropna()
    plt.figure(figsize=(7, 5))
    sns.scatterplot(data=scatter, x="mfe_pct", y="realized_pnl_pct", alpha=0.45)
    plt.title("MFE % vs Realized PnL %")
    plt.tight_layout()
    plt.savefig(out["charts"] / "mfe_vs_realized_pnl.png")
    plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table}
