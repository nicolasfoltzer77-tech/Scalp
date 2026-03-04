from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
try:
    import seaborn as sns
except Exception:  # optional plotting dependency
    sns = None
import sqlite3

from analysis import db


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades = db.load_table(conn, "recorder")
    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl"}

    tcol = db.pick_first(trades.columns, ["close_time", "ts_close", "open_time", "ts_open", "ts"])
    if tcol:
        trades["t"] = db.to_datetime_series(trades[tcol])
        trades = trades.sort_values("t")

    pnl = pd.to_numeric(trades[pnl_col], errors="coerce").fillna(0.0)
    trades["equity"] = pnl.cumsum()
    trades["peak"] = trades["equity"].cummax()
    trades["drawdown"] = trades["equity"] - trades["peak"]
    trades[[pnl_col, "equity", "drawdown"]].to_csv(out["csv"] / "equity_drawdown_series.csv", index=False)

    if sns:
        sns.set_theme(style="whitegrid")
    plt.figure(figsize=(10, 4))
    plt.plot(trades.index, trades["equity"])
    plt.title("Equity curve")
    plt.tight_layout()
    plt.savefig(out["charts"] / "equity_curve.png")
    plt.close()

    plt.figure(figsize=(10, 4))
    plt.plot(trades.index, trades["drawdown"], color="red")
    plt.title("Drawdown curve")
    plt.tight_layout()
    plt.savefig(out["charts"] / "drawdown_curve.png")
    plt.close()

    r = pnl
    sharpe = np.sqrt(len(r)) * (r.mean() / r.std()) if r.std() not in (0, np.nan) else np.nan
    downside = r[r < 0]
    sortino = np.sqrt(len(r)) * (r.mean() / downside.std()) if len(downside) > 1 and downside.std() > 0 else np.nan

    summary = pd.DataFrame([{
        "max_drawdown": trades["drawdown"].min(),
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
    }])
    summary.to_csv(out["csv"] / "equity_summary.csv", index=False)
    return {"status": "ok", "rows": len(trades), "max_drawdown": float(trades['drawdown'].min())}
