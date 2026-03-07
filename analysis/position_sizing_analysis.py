from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.position_sizing_analysis")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        reason = "trades table not found"
        log.warning(reason)
        return {"status": "skipped", "reason": reason}

    pnl_col = db.find_pnl_col(trades.columns)
    size_col = db.pick_first(trades.columns, ["size", "position_size", "qty", "quantity"])
    lev_col = db.find_leverage_col(trades.columns)
    if pnl_col is None:
        reason = "missing pnl column"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    skipped = []
    sns.set_theme(style="whitegrid")

    if size_col:
        work["size"] = pd.to_numeric(work[size_col], errors="coerce")
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="size", y="pnl", alpha=0.45)
        plt.title("Size vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "size_vs_pnl.png")
        plt.close()

        sized = work[["size", "pnl"]].dropna().copy()
        sized["size_bucket"] = pd.qcut(sized["size"], q=10, duplicates="drop")
        exp = sized.groupby("size_bucket", observed=False)["pnl"].mean().reset_index(name="expectancy")
        exp["bucket_mid"] = [b.mid if pd.notna(b) else None for b in exp["size_bucket"]]
        plt.figure(figsize=(8, 4))
        sns.lineplot(data=exp, x="bucket_mid", y="expectancy", marker="o")
        plt.title("Expectancy vs Size Bucket")
        plt.tight_layout()
        plt.savefig(out["charts"] / "expectancy_vs_size_bucket.png")
        plt.close()
    else:
        skipped.extend(["size_vs_pnl", "expectancy_vs_size_bucket"])
        log.warning("missing size column")

    if lev_col:
        work["leverage"] = pd.to_numeric(work[lev_col], errors="coerce")
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="leverage", y="pnl", alpha=0.45)
        plt.title("Leverage vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "leverage_vs_pnl.png")
        plt.close()
    else:
        skipped.append("leverage_vs_pnl")
        log.warning("missing leverage column")

    keep = [c for c in ["pnl", "size", "leverage"] if c in work.columns]
    if keep:
        work[keep].to_csv(out["csv"] / "position_sizing_analysis.csv", index=False)
    return {"status": "ok", "rows": int(work["pnl"].notna().sum()), "table": table, "skipped_graphs": skipped}
