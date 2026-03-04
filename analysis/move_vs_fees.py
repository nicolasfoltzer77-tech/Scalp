from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder_trades", "recorder"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    fee_col = db.find_fee_col(trades.columns)
    mfe_col = db.pick_first(trades.columns, ["mfe", "max_favorable_excursion"])
    mae_col = db.pick_first(trades.columns, ["mae", "max_adverse_excursion"])
    low_col = db.find_price_col(trades.columns, "low")
    high_col = db.find_price_col(trades.columns, "high")
    entry_col = db.find_price_col(trades.columns, "entry")
    close_col = db.find_price_col(trades.columns, "close")

    work = trades.copy()

    if not mfe_col and low_col and high_col and entry_col:
        e = pd.to_numeric(work[entry_col], errors="coerce")
        low = pd.to_numeric(work[low_col], errors="coerce")
        high = pd.to_numeric(work[high_col], errors="coerce")
        work["mfe"] = (high - e).abs()
        mfe_col = "mfe"

    if not mae_col and low_col and high_col and entry_col:
        e = pd.to_numeric(work[entry_col], errors="coerce")
        low = pd.to_numeric(work[low_col], errors="coerce")
        high = pd.to_numeric(work[high_col], errors="coerce")
        work["mae"] = (e - low).abs()
        mae_col = "mae"

    if not fee_col or not mfe_col or not mae_col:
        return {"status": "skipped", "reason": "missing fee/mfe/mae inputs", "table": table}

    work[fee_col] = pd.to_numeric(work[fee_col], errors="coerce").abs()
    work[mfe_col] = pd.to_numeric(work[mfe_col], errors="coerce").abs()
    work[mae_col] = pd.to_numeric(work[mae_col], errors="coerce").abs()

    if close_col and entry_col:
        work["expected_move"] = (pd.to_numeric(work[close_col], errors="coerce") - pd.to_numeric(work[entry_col], errors="coerce")).abs()
    else:
        work["expected_move"] = work[[mfe_col, mae_col]].mean(axis=1)

    avg_mfe = float(work[mfe_col].mean())
    avg_mae = float(work[mae_col].mean())
    avg_fees = float(work[fee_col].mean())
    avg_expected_move = float(work["expected_move"].mean())

    ratio = np.nan if avg_fees == 0 else float(avg_expected_move / avg_fees)
    metrics = pd.DataFrame([
        {
            "average_mfe": avg_mfe,
            "average_mae": avg_mae,
            "average_fees": avg_fees,
            "average_expected_move": avg_expected_move,
            "expected_move_to_fees_ratio": ratio,
            "profitable_after_fees": bool(avg_expected_move >= avg_fees) if not np.isnan(avg_fees) else False,
        }
    ])
    metrics.to_csv(out["csv"] / "move_vs_fees_metrics.csv", index=False)

    plt.figure(figsize=(7, 4.5))
    labels = ["Average MFE", "Average Fees"]
    values = [avg_mfe, avg_fees]
    colors = ["tab:blue", "tab:red"]
    plt.bar(labels, values, color=colors)
    plt.title("Average MFE vs Average Fees")
    plt.ylabel("Value")
    plt.tight_layout()
    plt.savefig(out["charts"] / "mfe_vs_fees.png")
    plt.close()

    return {"status": "ok", "rows": len(work), "table": table}
