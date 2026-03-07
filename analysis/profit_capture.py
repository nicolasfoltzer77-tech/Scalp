from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.profit_capture")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl_net"] = pd.to_numeric(work[pnl_col], errors="coerce")

    if "profit_capture_ratio" not in work.columns:
        if "mfe_price_distance" in work.columns:
            work["profit_capture_ratio"] = work["pnl_net"] / pd.to_numeric(work["mfe_price_distance"], errors="coerce").replace(0, pd.NA)
        else:
            log.warning("profit_capture_ratio unavailable")
            work["profit_capture_ratio"] = pd.NA

    for c in ("mfe_ratio", "mae_ratio", "profit_capture_ratio"):
        if c in work.columns:
            work[c] = pd.to_numeric(work[c], errors="coerce")

    metrics = work[["pnl_net", "mfe_ratio", "mae_ratio", "profit_capture_ratio"]].describe(include="all")
    metrics.to_csv(out["csv"] / "profit_capture_metrics.csv")

    sns.set_theme(style="whitegrid")
    vals = work["profit_capture_ratio"].dropna()
    plt.figure(figsize=(8, 4.5))
    if vals.empty:
        plt.text(0.5, 0.5, "No profit capture data", ha="center", va="center")
        plt.axis("off")
    else:
        sns.histplot(vals, bins=40, kde=True)
        plt.xlabel("profit_capture_ratio")
    plt.title("Profit Capture Distribution")
    plt.tight_layout()
    plt.savefig(out["charts"] / "profit_capture_distribution.png")
    plt.close()

    if all(c in work.columns for c in ("mfe_ratio", "pnl_net")):
        s = work[["mfe_ratio", "pnl_net"]].dropna()
        plt.figure(figsize=(7, 5))
        sns.scatterplot(data=s, x="mfe_ratio", y="pnl_net", alpha=0.4)
        plt.title("PnL vs MFE Ratio")
        plt.tight_layout()
        plt.savefig(out["charts"] / "pnl_vs_mfe.png")
        plt.close()

    if all(c in work.columns for c in ("mae_ratio", "pnl_net")):
        s = work[["mae_ratio", "pnl_net"]].dropna()
        plt.figure(figsize=(7, 5))
        sns.scatterplot(data=s, x="mae_ratio", y="pnl_net", alpha=0.4)
        plt.title("PnL vs MAE Ratio")
        plt.tight_layout()
        plt.savefig(out["charts"] / "pnl_vs_mae.png")
        plt.close()

    return {"status": "ok", "rows": int(work["pnl_net"].notna().sum()), "table": table}
