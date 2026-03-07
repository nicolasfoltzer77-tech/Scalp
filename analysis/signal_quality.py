from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.signal_quality")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl_net"] = pd.to_numeric(work[pnl_col], errors="coerce")

    for col in ("trigger_strength", "signal_age_ms"):
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    if "trigger_strength" in work.columns:
        s = work[["trigger_strength", "pnl_net"]].dropna()
        plt.figure(figsize=(7, 5))
        if s.empty:
            plt.text(0.5, 0.5, "No trigger_strength data", ha="center", va="center")
            plt.axis("off")
        else:
            sns.scatterplot(data=s, x="trigger_strength", y="pnl_net", alpha=0.4)
        plt.title("Trigger Strength vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "trigger_strength_vs_pnl.png")
        plt.close()
    else:
        log.warning("trigger_strength missing")

    if "signal_age_ms" in work.columns:
        s = work[["signal_age_ms", "pnl_net"]].dropna()
        plt.figure(figsize=(7, 5))
        if s.empty:
            plt.text(0.5, 0.5, "No signal_age_ms data", ha="center", va="center")
            plt.axis("off")
        else:
            sns.scatterplot(data=s, x="signal_age_ms", y="pnl_net", alpha=0.4)
        plt.title("Signal Age (ms) vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "signal_age_vs_pnl.png")
        plt.close()

    summary = work[[c for c in ["trigger_strength", "signal_age_ms", "pnl_net"] if c in work.columns]].describe(include="all")
    summary.to_csv(out["csv"] / "signal_quality_summary.csv")

    return {"status": "ok", "rows": int(work["pnl_net"].notna().sum()), "table": table}
