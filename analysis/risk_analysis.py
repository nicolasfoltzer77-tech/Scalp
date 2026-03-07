from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.risk_analysis")


def _max_drawdown_duration(drawdown: pd.Series) -> int:
    dur = 0
    max_dur = 0
    for v in drawdown.fillna(0):
        if v < 0:
            dur += 1
            max_dur = max(max_dur, dur)
        else:
            dur = 0
    return max_dur


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        reason = "trades table not found"
        log.warning(reason)
        return {"status": "skipped", "reason": reason}

    pnl_col = db.find_pnl_col(trades.columns)
    if pnl_col is None:
        reason = "missing pnl column"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    pnl = pd.to_numeric(trades[pnl_col], errors="coerce").fillna(0.0)
    if pnl.empty:
        reason = "no pnl rows available"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()
    dd_duration = _max_drawdown_duration(drawdown)

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(8, 4))
    sns.histplot(drawdown, bins=40, kde=True)
    plt.title("Drawdown Distribution")
    plt.tight_layout()
    plt.savefig(out["charts"] / "drawdown_distribution.png")
    plt.close()

    plt.figure(figsize=(8, 4))
    plt.bar(["max_dd_duration"], [dd_duration], color="#d62728")
    plt.title("Max Drawdown Duration")
    plt.tight_layout()
    plt.savefig(out["charts"] / "max_dd_duration.png")
    plt.close()

    plt.figure(figsize=(8, 4))
    tail = pnl[pnl < pnl.quantile(0.05)]
    sns.histplot(tail, bins=30, kde=True)
    plt.title("Tail Risk (Worst 5% Returns)")
    plt.tight_layout()
    plt.savefig(out["charts"] / "tail_risk.png")
    plt.close()

    pd.DataFrame({"pnl": pnl, "drawdown": drawdown}).to_csv(out["csv"] / "risk_analysis.csv", index=False)
    return {"status": "ok", "rows": int(len(pnl)), "max_dd_duration": int(dd_duration), "table": table}
