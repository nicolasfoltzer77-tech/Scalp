from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

try:
    import seaborn as sns
except Exception:
    sns = None

from analysis import db


def _profit_factor(pnl: pd.Series) -> float:
    profits = pnl[pnl > 0].sum()
    losses = pnl[pnl < 0].sum()
    if losses == 0:
        return float(np.inf) if profits > 0 else np.nan
    return float(profits / abs(losses))


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder_trades", "recorder"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    step_col = db.find_step_col(trades.columns)
    pnl_col = db.find_pnl_col(trades.columns)
    if not step_col or not pnl_col:
        return {"status": "skipped", "reason": "missing step or pnl column", "table": table}

    work = trades[[step_col, pnl_col]].copy()
    work[step_col] = pd.to_numeric(work[step_col], errors="coerce")
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    work = work.dropna(subset=[step_col, pnl_col])

    rows = []
    for step_value, sub in work.groupby(step_col, dropna=False):
        pnl = sub[pnl_col]
        rows.append({
            "step": int(step_value) if float(step_value).is_integer() else float(step_value),
            "trades": int(len(sub)),
            "winrate": float((pnl > 0).mean()),
            "expectancy": float(pnl.mean()),
            "profit_factor": _profit_factor(pnl),
        })

    out_df = pd.DataFrame(rows).sort_values("step")
    out_df.to_csv(out["csv"] / "expectancy_by_step_extended.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")

    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    x = out_df["step"]
    axes[0].plot(x, out_df["expectancy"], marker="o")
    axes[0].set_ylabel("Expectancy")
    axes[0].set_title("Expectancy / Winrate / Profit Factor by Step")

    axes[1].plot(x, out_df["winrate"], marker="o", color="tab:green")
    axes[1].set_ylabel("Winrate")

    pf = out_df["profit_factor"].replace(np.inf, np.nan)
    axes[2].plot(x, pf, marker="o", color="tab:orange")
    axes[2].set_ylabel("Profit Factor")
    axes[2].set_xlabel("Step")

    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_vs_step.png")
    plt.close(fig)

    return {"status": "ok", "rows": len(out_df), "table": table}
