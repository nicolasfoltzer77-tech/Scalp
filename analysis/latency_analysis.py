from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.latency_analysis")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl_net"] = pd.to_numeric(work[pnl_col], errors="coerce")

    if "entry_delay_ms" not in work.columns:
        open_col = db.pick_first(work.columns, ["ts_open", "open_time", "ts_entry"])
        signal_col = db.pick_first(work.columns, ["ts_signal", "signal_ts", "ts_sig", "signal_time"])
        if open_col and signal_col:
            work["entry_delay_ms"] = pd.to_numeric(work[open_col], errors="coerce") - pd.to_numeric(work[signal_col], errors="coerce")
        else:
            return {"status": "skipped", "reason": "missing entry_delay_ms and open/signal timestamps", "table": table}

    work["entry_delay_ms"] = pd.to_numeric(work["entry_delay_ms"], errors="coerce")
    plot = work[["entry_delay_ms", "pnl_net"]].dropna()
    plot = plot[plot["entry_delay_ms"] >= 0]

    plt.figure(figsize=(7, 5))
    if plot.empty:
        plt.text(0.5, 0.5, "No entry delay data", ha="center", va="center")
        plt.axis("off")
    else:
        sns.scatterplot(data=plot, x="entry_delay_ms", y="pnl_net", alpha=0.4)
    plt.title("Entry Delay (ms) vs PnL")
    plt.tight_layout()
    plt.savefig(out["charts"] / "entry_delay_vs_pnl.png")
    plt.close()

    plot.describe(include="all").to_csv(out["csv"] / "latency_analysis_summary.csv")
    return {"status": "ok", "rows": int(len(plot)), "table": table}
