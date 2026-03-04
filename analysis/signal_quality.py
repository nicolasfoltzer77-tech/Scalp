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


def _as_bool_flag(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return numeric.fillna(0).astype(float) > 0
    return series.astype(str).str.lower().isin({"1", "true", "yes", "y"})


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    pyramide_col = db.pick_first(trades.columns, ["nb_pyramide", "pyramide_count", "pyramid_count"])
    signal_cols = [
        c for c in ["momentum_ok", "prebreak_ok", "pullback_ok", "compression_ok"] if c in set(trades.columns)
    ]

    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")

    rows = []
    for signal in signal_cols:
        mask = _as_bool_flag(work[signal])
        pnl = work.loc[mask, pnl_col].dropna()
        if pnl.empty:
            continue
        profits = pnl[pnl > 0].sum()
        losses = pnl[pnl < 0].sum()
        pf = np.inf if losses == 0 and profits > 0 else (profits / abs(losses) if losses != 0 else np.nan)
        rows.append(
            {
                "signal": signal,
                "trades": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "profit_factor": float(pf) if pd.notna(pf) else np.nan,
            }
        )

    signal_summary = pd.DataFrame(rows)
    signal_summary.to_csv(out["csv"] / "signal_expectancy.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    if signal_summary.empty:
        plt.text(0.5, 0.5, "No signal data", ha="center", va="center")
        plt.axis("off")
    else:
        plt.bar(signal_summary["signal"], signal_summary["expectancy"], color="tab:green")
        plt.xticks(rotation=15)
        plt.ylabel("Expectancy")
    plt.title("Signal Expectancy (flag == 1)")
    plt.tight_layout()
    plt.savefig(out["charts"] / "signal_expectancy_bar.png")
    plt.close()

    pyramiding_rows = 0
    if pyramide_col:
        work[pyramide_col] = pd.to_numeric(work[pyramide_col], errors="coerce")
        work["pyramide_bucket"] = pd.cut(
            work[pyramide_col],
            bins=[-0.1, 0.5, 1.5, 2.5, 3.5, np.inf],
            labels=["0", "1", "2", "3", "4+"],
        )
        pyra_summary = db.compute_basic_metrics(work.dropna(subset=[pyramide_col, pnl_col]), pnl_col, ["pyramide_bucket"])
        order = {"0": 0, "1": 1, "2": 2, "3": 3, "4+": 4}
        pyra_summary = pyra_summary.sort_values("pyramide_bucket", key=lambda s: s.astype(str).map(order))
        pyra_summary.to_csv(out["csv"] / "pyramiding_edge.csv", index=False)

        plt.figure(figsize=(8, 4.5))
        plt.bar(pyra_summary["pyramide_bucket"].astype(str), pyra_summary["expectancy"], color="tab:orange")
        plt.title("Pyramiding Edge (Expectancy by Pyramide Count)")
        plt.xlabel("Pyramide bucket")
        plt.ylabel("Expectancy")
        plt.tight_layout()
        plt.savefig(out["charts"] / "pyramiding_edge.png")
        plt.close()
        pyramiding_rows = len(pyra_summary)

    return {
        "status": "ok",
        "table": table,
        "signals": len(signal_summary),
        "pyramiding_buckets": pyramiding_rows,
    }
