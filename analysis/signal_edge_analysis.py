from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.signal_edge_analysis")


def _score_col(cols: pd.Index) -> str | None:
    return db.pick_first(cols, ["score", "signal_score", "entry_score", "quality_score", "model_score", "score_C"])


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    pnl_col = db.find_pnl_col(trades.columns)
    score_col = _score_col(trades.columns)
    if not pnl_col or not score_col:
        return {"status": "skipped", "reason": "missing pnl or score column", "table": table}

    work = trades.copy()
    work["pnl"] = pd.to_numeric(work[pnl_col], errors="coerce")
    work["score"] = pd.to_numeric(work[score_col], errors="coerce")
    work = work.dropna(subset=["pnl", "score"])
    if work.empty:
        return {"status": "skipped", "reason": "no numeric pnl/score rows", "table": table}

    work["score_bucket"] = pd.qcut(work["score"], q=min(10, work["score"].nunique()), duplicates="drop")
    metrics = db.compute_basic_metrics(work, "pnl", ["score_bucket"])
    metrics.to_csv(out["csv"] / "signal_edge_metrics.csv", index=False)

    sns.set_theme(style="whitegrid")

    for y, fname, title in [
        ("expectancy", "expectancy_vs_score.png", "Expectancy vs Score"),
        ("winrate", "winrate_vs_score.png", "Winrate vs Score"),
        ("profit_factor", "profit_factor_vs_score.png", "Profit Factor vs Score"),
    ]:
        if metrics.empty or y not in metrics.columns:
            log.warning("Skipping %s: no aggregated metrics", fname)
            continue
        plt.figure(figsize=(9, 4.8))
        plt.plot(range(len(metrics)), metrics[y].values, marker="o")
        plt.xticks(range(len(metrics)), metrics["score_bucket"].astype(str), rotation=45, ha="right")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(out["charts"] / fname)
        plt.close()

    plt.figure(figsize=(8, 4.8))
    sns.histplot(work["score"], bins=40, kde=True)
    plt.title("Score Distribution")
    plt.tight_layout()
    plt.savefig(out["charts"] / "score_distribution.png")
    plt.close()

    calib = work.copy()
    calib["pred_win_prob"] = (calib["score"] - calib["score"].min()) / (calib["score"].max() - calib["score"].min() + 1e-9)
    calib["realized_win"] = calib["pnl"].gt(0).astype(int)
    calib["prob_bucket"] = pd.qcut(calib["pred_win_prob"], q=min(10, calib["pred_win_prob"].nunique()), duplicates="drop")
    curve = calib.groupby("prob_bucket", observed=False).agg(pred=("pred_win_prob", "mean"), obs=("realized_win", "mean")).dropna()
    if curve.empty:
        log.warning("Skipping score_calibration_curve: insufficient probability buckets")
    else:
        plt.figure(figsize=(6, 6))
        plt.plot(curve["pred"], curve["obs"], marker="o")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
        plt.title("Score Calibration Curve")
        plt.xlabel("Predicted win probability")
        plt.ylabel("Observed win rate")
        plt.tight_layout()
        plt.savefig(out["charts"] / "score_calibration_curve.png")
        plt.close()



    # Entry diagnostics
    entry_col = db.pick_first(work.columns, ["entry_distance", "entry_distance_pct", "distance_to_signal"])
    if entry_col:
        work["entry_distance"] = pd.to_numeric(work[entry_col], errors="coerce")
        s = work[["entry_distance", "pnl"]].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.scatterplot(data=s, x="entry_distance", y="pnl", alpha=0.35)
            plt.title("Entry Distance vs PnL")
            plt.tight_layout()
            plt.savefig(out["charts"] / "entry_distance_vs_pnl.png")
            plt.close()

            s = s.sort_values("entry_distance")
            s["entry_eff"] = s["pnl"].expanding().mean()
            plt.figure(figsize=(9, 4.8))
            plt.plot(s["entry_distance"].values, s["entry_eff"].values)
            plt.title("Entry Efficiency")
            plt.xlabel("Entry distance")
            plt.ylabel("Cumulative expectancy")
            plt.tight_layout()
            plt.savefig(out["charts"] / "entry_efficiency.png")
            plt.close()
        else:
            log.warning("Skipping entry_distance charts: no numeric rows")
    else:
        log.warning("Skipping entry_distance_vs_pnl/entry_efficiency: missing entry distance column")

    mid_col = db.pick_first(work.columns, ["mid_price", "mid", "mark_price", "reference_price"])
    entry_price_col = db.find_price_col(work.columns, "entry")
    if mid_col and entry_price_col:
        work["mid_price"] = pd.to_numeric(work[mid_col], errors="coerce")
        work["entry_price"] = pd.to_numeric(work[entry_price_col], errors="coerce")
        s = work[["entry_price", "mid_price"]].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.scatterplot(data=s, x="mid_price", y="entry_price", alpha=0.35)
            plt.title("Entry vs Midprice")
            plt.tight_layout()
            plt.savefig(out["charts"] / "entry_vs_midprice.png")
            plt.close()
        else:
            log.warning("Skipping entry_vs_midprice: no numeric rows")
    else:
        log.warning("Skipping entry_vs_midprice: missing mid/entry price columns")

    # Execution diagnostics
    delay_col = db.pick_first(work.columns, ["entry_delay_ms", "entry_delay", "delay_ms"])
    if delay_col:
        work["entry_delay"] = pd.to_numeric(work[delay_col], errors="coerce")
        s = work[["entry_delay", "pnl"]].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.scatterplot(data=s, x="entry_delay", y="pnl", alpha=0.35)
            plt.title("Entry Delay vs PnL")
            plt.tight_layout()
            plt.savefig(out["charts"] / "entry_delay_vs_pnl.png")
            plt.close()
        else:
            log.warning("Skipping entry_delay_vs_pnl: no numeric rows")
    else:
        log.warning("Skipping entry_delay_vs_pnl: missing delay column")

    latency_col = db.pick_first(work.columns, ["latency_ms", "latency", "execution_latency_ms"])
    if latency_col:
        work["latency"] = pd.to_numeric(work[latency_col], errors="coerce")
        s = work[["latency", "pnl"]].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.scatterplot(data=s, x="latency", y="pnl", alpha=0.35)
            plt.title("Latency vs PnL")
            plt.tight_layout()
            plt.savefig(out["charts"] / "latency_vs_pnl.png")
            plt.close()
        else:
            log.warning("Skipping latency_vs_pnl: no numeric rows")
    else:
        log.warning("Skipping latency_vs_pnl: missing latency column")

    slippage_col = db.pick_first(work.columns, ["slippage", "slippage_bps", "entry_slippage"])
    if slippage_col:
        work["slippage"] = pd.to_numeric(work[slippage_col], errors="coerce")
        s = work["slippage"].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.histplot(s, bins=40, kde=True)
            plt.title("Slippage Distribution")
            plt.tight_layout()
            plt.savefig(out["charts"] / "slippage_distribution.png")
            plt.close()
        else:
            log.warning("Skipping slippage_distribution: no numeric rows")
    else:
        log.warning("Skipping slippage_distribution: missing slippage column")

    # Profit-capture diagnostics
    mfe_col = db.pick_first(work.columns, ["mfe_ratio", "mfe", "mfe_price_distance"])
    mae_col = db.pick_first(work.columns, ["mae_ratio", "mae", "mae_price_distance"])

    if mfe_col:
        work["mfe"] = pd.to_numeric(work[mfe_col], errors="coerce")
        s = work[["mfe", "pnl"]].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.scatterplot(data=s, x="mfe", y="pnl", alpha=0.35)
            plt.title("PnL vs MFE")
            plt.tight_layout()
            plt.savefig(out["charts"] / "pnl_vs_mfe.png")
            plt.close()

            plt.figure(figsize=(8, 4.8))
            sns.histplot(work["mfe"].dropna(), bins=40, kde=True)
            plt.title("MFE Distribution")
            plt.tight_layout()
            plt.savefig(out["charts"] / "mfe_distribution.png")
            plt.close()
    else:
        log.warning("Skipping pnl_vs_mfe/mfe_distribution: missing MFE column")

    if mae_col:
        work["mae"] = pd.to_numeric(work[mae_col], errors="coerce")
        s = work[["mae", "pnl"]].dropna()
        if not s.empty:
            plt.figure(figsize=(8, 4.8))
            sns.scatterplot(data=s, x="mae", y="pnl", alpha=0.35)
            plt.title("PnL vs MAE")
            plt.tight_layout()
            plt.savefig(out["charts"] / "pnl_vs_mae.png")
            plt.close()

            plt.figure(figsize=(8, 4.8))
            sns.histplot(work["mae"].dropna(), bins=40, kde=True)
            plt.title("MAE Distribution")
            plt.tight_layout()
            plt.savefig(out["charts"] / "mae_distribution.png")
            plt.close()
    else:
        log.warning("Skipping pnl_vs_mae/mae_distribution: missing MAE column")

    if mfe_col:
        capture = work[["pnl", "mfe"]].dropna().copy()
        capture["profit_capture_ratio"] = capture["pnl"] / capture["mfe"].replace(0, pd.NA)
        c = capture["profit_capture_ratio"].dropna()
        if not c.empty:
            plt.figure(figsize=(8, 4.8))
            sns.histplot(c, bins=40, kde=True)
            plt.title("Profit Capture Ratio")
            plt.tight_layout()
            plt.savefig(out["charts"] / "profit_capture_ratio.png")
            plt.close()
        else:
            log.warning("Skipping profit_capture_ratio: no non-zero MFE rows")
    else:
        log.warning("Skipping profit_capture_ratio: missing MFE column")

    return {"status": "ok", "rows": int(len(work)), "table": table}
