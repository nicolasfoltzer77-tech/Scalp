from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.entry_quality")


def _expectancy_by_bucket(frame: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    grouped = frame.groupby(bucket_col, dropna=True, observed=False)["pnl_net"]
    out = grouped.agg(trades="count", expectancy="mean").reset_index()
    return out


def run(conn: sqlite3.Connection, out: dict) -> dict:
    try:
        trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
        if trades is None:
            return {"status": "skipped", "reason": "trades table not found"}

        pnl_col = db.find_pnl_col(trades.columns)
        if not pnl_col:
            return {"status": "skipped", "reason": "missing pnl column", "table": table}

        needed = ["score_C", "s_struct", "s_timing", "entry_distance_atr", "entry_range_pos", "mfe_ratio"]
        available = [c for c in needed if c in trades.columns]

        work = trades[[pnl_col] + available].copy()
        work = work.rename(columns={pnl_col: "pnl_net"})
        for c in ["pnl_net"] + available:
            work[c] = pd.to_numeric(work[c], errors="coerce")
        work = work.dropna(subset=["pnl_net"])
        if work.empty:
            return {"status": "skipped", "reason": "no valid pnl rows", "table": table}

        if "entry_distance_atr" in work.columns:
            work["entry_distance_bucket"] = pd.cut(work["entry_distance_atr"], bins=[0, 0.25, 0.5, 1.0, 2.0, float("inf")], right=False)
            exp_dist = _expectancy_by_bucket(work.dropna(subset=["entry_distance_bucket"]), "entry_distance_bucket")
            exp_dist.to_csv(out["csv"] / "expectancy_vs_entry_distance.csv", index=False)
            plt.figure(figsize=(8, 4.5))
            sns.barplot(data=exp_dist, x="entry_distance_bucket", y="expectancy")
            plt.xticks(rotation=20)
            plt.title("Expectancy vs Entry Distance (ATR)")
            plt.tight_layout()
            plt.savefig(out["charts"] / "expectancy_vs_entry_distance.png")
            plt.close()
        else:
            log.warning("entry_distance_atr missing; skipping expectancy_vs_entry_distance")

        if "entry_range_pos" in work.columns:
            work["entry_range_bucket"] = pd.cut(work["entry_range_pos"], bins=[0, 0.2, 0.4, 0.6, 0.8, 1.01], right=False)
            exp_pos = _expectancy_by_bucket(work.dropna(subset=["entry_range_bucket"]), "entry_range_bucket")
            exp_pos.to_csv(out["csv"] / "expectancy_vs_range_pos.csv", index=False)
            plt.figure(figsize=(8, 4.5))
            sns.barplot(data=exp_pos, x="entry_range_bucket", y="expectancy")
            plt.xticks(rotation=20)
            plt.title("Expectancy vs Entry Range Position")
            plt.tight_layout()
            plt.savefig(out["charts"] / "expectancy_vs_range_pos.png")
            plt.close()
        else:
            log.warning("entry_range_pos missing; skipping expectancy_vs_range_pos")

        if all(c in work.columns for c in ["score_C", "mfe_ratio"]):
            plot = work[["score_C", "mfe_ratio"]].dropna()
            plt.figure(figsize=(7, 5))
            sns.scatterplot(data=plot, x="score_C", y="mfe_ratio", alpha=0.45)
            plt.title("MFE Ratio vs Score_C")
            plt.tight_layout()
            plt.savefig(out["charts"] / "mfe_vs_score_C.png")
            plt.close()

        group_cols = [c for c in ["score_C", "s_struct", "s_timing", "entry_distance_atr", "entry_range_pos"] if c in work.columns]
        if group_cols:
            grouped = work[group_cols + ["pnl_net"]].copy().dropna()
            if not grouped.empty:
                grouped[group_cols] = grouped[group_cols].round(2)
                summary = grouped.groupby(group_cols, observed=False)["pnl_net"].agg(["count", "mean"]).reset_index()
                summary.columns = group_cols + ["trades", "expectancy"]
                summary.to_csv(out["csv"] / "entry_quality_expectancy_groups.csv", index=False)

        return {"status": "ok", "rows": int(len(work)), "table": table}
    except Exception as exc:
        log.warning("entry_quality failed: %s", exc)
        return {"status": "skipped", "reason": str(exc)}
