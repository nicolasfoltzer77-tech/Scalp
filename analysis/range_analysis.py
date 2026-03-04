from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis import db


RANGE_BUCKETS = [0.0, 0.002, 0.005, 0.01, np.inf]
RANGE_LABELS = ["0-0.2%", "0.2-0.5%", "0.5-1%", "1%+"]


def _profit_factor(pnl: pd.Series) -> float:
    profits = pnl[pnl > 0].sum()
    losses = pnl[pnl < 0].sum()
    if losses == 0:
        return float("inf") if profits > 0 else float("nan")
    return float(profits / abs(losses))


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    cols = trades.columns
    entry_col = db.find_price_col(cols, "entry")
    high_col = db.find_price_col(cols, "high")
    low_col = db.find_price_col(cols, "low")
    pnl_col = db.find_pnl_col(cols)

    if not all([entry_col, high_col, low_col, pnl_col]):
        return {
            "status": "skipped",
            "reason": "missing one of entry/high/low/pnl columns",
            "required": {
                "entry": entry_col,
                "high": high_col,
                "low": low_col,
                "pnl": pnl_col,
            },
        }

    frame = trades[[entry_col, high_col, low_col, pnl_col]].copy()
    frame = frame.rename(
        columns={entry_col: "entry_price", high_col: "high_price", low_col: "low_price", pnl_col: "pnl"}
    )
    frame[["entry_price", "high_price", "low_price", "pnl"]] = frame[
        ["entry_price", "high_price", "low_price", "pnl"]
    ].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["entry_price", "high_price", "low_price", "pnl"])
    frame = frame[frame["entry_price"] > 0]

    if frame.empty:
        return {"status": "skipped", "reason": "no valid rows for range analysis"}

    frame["range_expansion"] = (frame["high_price"] - frame["low_price"]) / frame["entry_price"]
    frame["range_bucket"] = pd.cut(frame["range_expansion"], bins=RANGE_BUCKETS, labels=RANGE_LABELS, right=False)

    rows: list[dict] = []
    for bucket in RANGE_LABELS:
        sub = frame[frame["range_bucket"] == bucket]
        pnl = sub["pnl"].dropna()
        if pnl.empty:
            rows.append(
                {
                    "range_bucket": bucket,
                    "trade_count": 0,
                    "winrate": np.nan,
                    "expectancy": np.nan,
                    "profit_factor": np.nan,
                }
            )
            continue
        rows.append(
            {
                "range_bucket": bucket,
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "profit_factor": _profit_factor(pnl),
            }
        )

    metrics = pd.DataFrame(rows)
    metrics.to_csv(out["csv"] / "range_expectancy.csv", index=False)

    plot_data = metrics.dropna(subset=["expectancy"])
    plt.figure(figsize=(8, 4))
    if plot_data.empty:
        plt.text(0.5, 0.5, "No valid range metrics", ha="center", va="center")
        plt.xticks([])
        plt.yticks([])
    else:
        plt.bar(plot_data["range_bucket"], plot_data["expectancy"])
        plt.axhline(0.0, color="black", linewidth=1, linestyle="--")
        plt.ylabel("Expectancy")
    plt.xlabel("Range expansion bucket")
    plt.title("Expectancy vs range expansion")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_range.png")
    plt.close()

    return {"status": "ok", "rows": len(metrics), "valid_rows": int(metrics["trade_count"].sum())}
