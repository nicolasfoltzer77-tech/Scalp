from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.risk_analysis")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    work = work.dropna(subset=["pnl"]).copy()
    if work.empty:
        return {"status": "skipped", "reason": "no numeric pnl rows", "table": table}

    equity = work["pnl"].cumsum()
    dd = equity - equity.cummax()
    dd_duration = dd.lt(0).astype(int).groupby(dd.ge(0).cumsum()).cumsum()

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4.8))
    sns.histplot(dd, bins=40, kde=True, color="#b91c1c")
    plt.title("Drawdown Distribution")
    plt.xlabel("Drawdown")
    plt.tight_layout()
    plt.savefig(out["charts"] / "drawdown_distribution.png")
    plt.close()

    plt.figure(figsize=(9, 4.8))
    plt.plot(dd_duration.values, color="#9333ea")
    plt.title("Max Drawdown Duration Progression")
    plt.xlabel("Trades")
    plt.ylabel("Consecutive DD trades")
    plt.tight_layout()
    plt.savefig(out["charts"] / "max_dd_duration.png")
    plt.close()

    losses = work["pnl"][work["pnl"] < 0]
    if losses.empty:
        log.warning("Skipping tail_risk: no losing trades")
    else:
        q05, q01 = np.quantile(losses, [0.05, 0.01])
        plt.figure(figsize=(8, 4.8))
        sns.histplot(losses, bins=40, color="#334155")
        plt.axvline(q05, color="#f59e0b", linestyle="--", label=f"5% VaR={q05:.3f}")
        plt.axvline(q01, color="#ef4444", linestyle="--", label=f"1% VaR={q01:.3f}")
        plt.title("Tail Risk (Loss Distribution)")
        plt.xlabel("PnL")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out["charts"] / "tail_risk.png")
        plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table, "max_dd_duration": int(dd_duration.max())}
