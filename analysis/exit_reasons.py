from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
try:
    import seaborn as sns
except Exception:  # optional plotting dependency
    sns = None
import sqlite3

from . import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    steps = db.load_table(conn, "recorder_steps")
    if "exec_type" not in steps.columns:
        return {"status": "skipped", "reason": "missing exec_type"}

    close = steps[steps["exec_type"].astype(str).str.lower() == "close"].copy()
    if close.empty:
        return {"status": "skipped", "reason": "no close steps"}

    reason_col = db.pick_first(close.columns, ["reason", "close_reason", "exit_reason", "status"])
    pnl_col = db.find_pnl_col(close.columns)
    if not reason_col or not pnl_col:
        return {"status": "skipped", "reason": "missing close reason or pnl"}

    close[pnl_col] = pd.to_numeric(close[pnl_col], errors="coerce")
    g = close.groupby(reason_col)[pnl_col]
    metrics = pd.DataFrame({
        "count": g.size(),
        "avg_pnl": g.mean(),
        "total_pnl": g.sum(),
        "winrate": g.apply(lambda s: (s > 0).mean()),
    }).reset_index().rename(columns={reason_col: "close_reason"})
    metrics.to_csv(out["csv"] / "close_reason_metrics.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 4))
    _sorted = metrics.sort_values("total_pnl", ascending=False)
    if sns:
        sns.barplot(data=_sorted, x="close_reason", y="total_pnl")
    else:
        plt.bar(_sorted["close_reason"].astype(str), _sorted["total_pnl"])
    plt.xticks(rotation=25, ha="right")
    plt.title("PnL by close reason")
    plt.tight_layout()
    plt.savefig(out["charts"] / "pnl_by_close_reason.png")
    plt.close()

    return {"status": "ok", "rows": len(metrics)}
