from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.performance_analysis")


def _pick_time_col(columns: pd.Index) -> str | None:
    open_col, close_col = db.find_open_close_time_cols(columns)
    return close_col or open_col


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    time_col = _pick_time_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    if time_col:
        work["ts"] = db.to_datetime_series(work[time_col])
    else:
        log.warning("No timestamp column found; using trade order for rolling charts")
        work["ts"] = pd.RangeIndex(len(work))

    work = work.dropna(subset=["pnl"]).copy()
    if work.empty:
        return {"status": "skipped", "reason": "no numeric pnl rows", "table": table}

    if pd.api.types.is_datetime64_any_dtype(work["ts"]):
        work = work.sort_values("ts")
    else:
        work = work.reset_index(drop=True)

    window = max(20, min(100, len(work) // 5 if len(work) > 50 else 20))
    work["equity"] = work["pnl"].cumsum()
    running_max = work["equity"].cummax()
    work["drawdown"] = work["equity"] - running_max

    r = work["pnl"]
    roll_mean = r.rolling(window).mean()
    roll_std = r.rolling(window).std().replace(0, pd.NA)
    work["rolling_sharpe"] = (roll_mean / roll_std) * (window ** 0.5)
    work["rolling_expectancy"] = roll_mean
    work["rolling_winrate"] = r.gt(0).rolling(window).mean()

    sns.set_theme(style="whitegrid")

    plt.figure(figsize=(10, 4.8))
    plt.plot(work["equity"].values, color="#2563eb", linewidth=1.8)
    plt.title("Equity Curve")
    plt.xlabel("Trades")
    plt.ylabel("Cumulative PnL")
    plt.tight_layout()
    plt.savefig(out["charts"] / "equity_curve.png")
    plt.close()

    plt.figure(figsize=(10, 4.8))
    plt.plot(work["drawdown"].values, color="#dc2626", linewidth=1.6)
    plt.fill_between(range(len(work)), work["drawdown"].values, 0, color="#fecaca", alpha=0.6)
    plt.title("Drawdown Curve")
    plt.xlabel("Trades")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.savefig(out["charts"] / "drawdown_curve.png")
    plt.close()

    for col, fname, title in [
        ("rolling_sharpe", "rolling_sharpe.png", "Rolling Sharpe"),
        ("rolling_expectancy", "rolling_expectancy.png", "Rolling Expectancy"),
        ("rolling_winrate", "rolling_winrate.png", "Rolling Winrate"),
    ]:
        vals = work[col].dropna()
        if vals.empty:
            log.warning("Skipping %s: insufficient rows for rolling window=%s", fname, window)
            continue
        plt.figure(figsize=(10, 4.8))
        plt.plot(vals.values, linewidth=1.8)
        plt.title(title)
        plt.xlabel("Trades")
        plt.ylabel(col)
        plt.tight_layout()
        plt.savefig(out["charts"] / fname)
        plt.close()

    return {"status": "ok", "rows": int(len(work)), "table": table, "rolling_window": window}
