from __future__ import annotations

import sqlite3
import logging

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.regime_analysis")


def _col(cols: pd.Index, candidates: list[str]) -> str | None:
    return db.pick_first(cols, candidates)


def _plot_metric(df: pd.DataFrame, x_col: str, y_col: str, title: str, out_path) -> bool:
    if x_col not in df.columns or y_col not in df.columns:
        return False
    s = df[[x_col, y_col]].dropna()
    if s.empty:
        return False
    plt.figure(figsize=(8, 4.8))
    sns.regplot(data=s, x=x_col, y=y_col, scatter_kws={"alpha": 0.35, "s": 25}, line_kws={"color": "#dc2626"})
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    return True


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    if not pnl_col:
        return {"status": "skipped", "reason": "missing pnl column", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    work["volatility"] = pd.to_numeric(_col(work.columns, ["volatility", "realized_vol", "volatility_20", "vol_regime"]), errors="coerce")
    work["atr"] = pd.to_numeric(_col(work.columns, ["atr", "atr_value", "atr_14"]), errors="coerce")
    work["trend"] = pd.to_numeric(_col(work.columns, ["trend_strength", "trend", "adx", "regime_trend"]), errors="coerce")

    sns.set_theme(style="whitegrid")
    plotted = 0

    if _plot_metric(work, "volatility", "pnl", "Expectancy vs Volatility", out["charts"] / "expectancy_vs_volatility.png"):
        plotted += 1
    else:
        log.warning("Skipping expectancy_vs_volatility: missing volatility data")

    if _plot_metric(work, "atr", "pnl", "Expectancy vs ATR", out["charts"] / "expectancy_vs_atr.png"):
        plotted += 1
    else:
        log.warning("Skipping expectancy_vs_atr: missing ATR data")

    if _plot_metric(work, "trend", "pnl", "Expectancy vs Trend", out["charts"] / "expectancy_vs_trend.png"):
        plotted += 1
    else:
        log.warning("Skipping expectancy_vs_trend: missing trend data")

    return {"status": "ok" if plotted else "skipped", "rows": int(work["pnl"].notna().sum()), "table": table, "charts": plotted}
