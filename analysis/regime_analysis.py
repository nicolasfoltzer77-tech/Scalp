from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.regime_analysis")


def _plot_expectancy_vs(work: pd.DataFrame, x_col: str, out_name: str, out: dict) -> None:
    binned = work[[x_col, "pnl"]].dropna().copy()
    if binned.empty:
        raise ValueError(f"no rows for {x_col}")
    binned["bucket"] = pd.qcut(binned[x_col], q=10, duplicates="drop")
    agg = binned.groupby("bucket", observed=False)["pnl"].mean().reset_index(name="expectancy")
    agg["x"] = [b.mid if pd.notna(b) else None for b in agg["bucket"]]
    plt.figure(figsize=(8, 4))
    sns.lineplot(data=agg, x="x", y="expectancy", marker="o")
    plt.title(out_name.replace("_", " ").title())
    plt.tight_layout()
    plt.savefig(out["charts"] / f"{out_name}.png")
    plt.close()


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

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")

    col_map = {
        "expectancy_vs_volatility": db.pick_first(work.columns, ["volatility", "vol", "realized_vol"]),
        "expectancy_vs_atr": db.pick_first(work.columns, ["atr", "atr_value", "atr_14"]),
        "expectancy_vs_trend": db.pick_first(work.columns, ["trend_strength", "trend", "adx"]),
    }

    sns.set_theme(style="whitegrid")
    skipped = []
    for out_name, col in col_map.items():
        if col is None:
            skipped.append(out_name)
            log.warning("missing column for %s", out_name)
            continue
        work[col] = pd.to_numeric(work[col], errors="coerce")
        try:
            _plot_expectancy_vs(work.rename(columns={col: out_name}), out_name, out_name, out)
        except Exception as exc:
            skipped.append(out_name)
            log.warning("skipping %s: %s", out_name, exc)

    cols = ["pnl"] + [c for c in col_map.values() if c is not None]
    work[cols].to_csv(out["csv"] / "regime_analysis.csv", index=False)
    return {"status": "ok", "rows": int(work["pnl"].notna().sum()), "table": table, "skipped_graphs": skipped}
