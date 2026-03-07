from __future__ import annotations

import logging
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from analysis import db

log = logging.getLogger("analysis.signal_edge_analysis")


def _score_col(cols) -> str | None:
    return db.pick_first(cols, ["score", "signal_score", "trigger_strength", "edge_score"])


def _safe_numeric(df: pd.DataFrame, col: str | None) -> pd.Series:
    if col is None or col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        reason = "trades table not found"
        log.warning(reason)
        return {"status": "skipped", "reason": reason}

    pnl_col = db.find_pnl_col(trades.columns)
    score_col = _score_col(trades.columns)
    if pnl_col is None:
        reason = "missing pnl column"
        log.warning(reason)
        return {"status": "skipped", "reason": reason, "table": table}

    sns.set_theme(style="whitegrid")
    work = trades.copy()
    work["pnl"] = _safe_numeric(work, pnl_col)
    skipped: list[str] = []

    # Signal edge charts
    if score_col is not None:
        work["score"] = _safe_numeric(work, score_col)
        bins = pd.qcut(work["score"], q=10, duplicates="drop")
        grp = work.groupby(bins, observed=False)
        agg = grp["pnl"].agg(["mean", lambda s: (s > 0).mean(), lambda s: s[s > 0].sum() / abs(s[s < 0].sum()) if (s < 0).any() else np.nan]).reset_index()
        agg.columns = ["bucket", "expectancy", "winrate", "profit_factor"]
        agg["score_mid"] = [b.mid if pd.notna(b) else np.nan for b in agg["bucket"]]

        for y, name in [("expectancy", "expectancy_vs_score"), ("winrate", "winrate_vs_score"), ("profit_factor", "profit_factor_vs_score")]:
            plt.figure(figsize=(8, 4))
            sns.lineplot(data=agg, x="score_mid", y=y, marker="o")
            plt.title(name.replace("_", " ").title())
            plt.tight_layout()
            plt.savefig(out["charts"] / f"{name}.png")
            plt.close()

        plt.figure(figsize=(8, 4))
        sns.histplot(work["score"].dropna(), bins=30, kde=True)
        plt.title("Score Distribution")
        plt.tight_layout()
        plt.savefig(out["charts"] / "score_distribution.png")
        plt.close()

        calib = work.dropna(subset=["score", "pnl"]).copy()
        calib["pred_bin"] = pd.qcut(calib["score"], q=10, duplicates="drop")
        c = calib.groupby("pred_bin", observed=False).agg(pred=("score", "mean"), actual=("pnl", lambda s: (s > 0).mean())).reset_index()
        plt.figure(figsize=(6, 6))
        sns.scatterplot(data=c, x="pred", y="actual")
        plt.plot([c["pred"].min(), c["pred"].max()], [c["pred"].min(), c["pred"].max()], "r--", linewidth=1)
        plt.title("Score Calibration Curve")
        plt.tight_layout()
        plt.savefig(out["charts"] / "score_calibration_curve.png")
        plt.close()
    else:
        skipped.extend(["expectancy_vs_score", "winrate_vs_score", "profit_factor_vs_score", "score_distribution", "score_calibration_curve"])
        log.warning("missing score column")

    # Entry charts
    entry_distance_col = db.pick_first(work.columns, ["entry_distance", "distance_to_signal", "entry_distance_pct"])
    if entry_distance_col:
        work["entry_distance"] = _safe_numeric(work, entry_distance_col)
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="entry_distance", y="pnl", alpha=0.45)
        plt.title("Entry Distance vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "entry_distance_vs_pnl.png")
        plt.close()
    else:
        skipped.append("entry_distance_vs_pnl")
        log.warning("missing entry distance column")

    side_col = db.find_side_col(work.columns)
    entry_col = db.find_price_col(work.columns, "entry")
    mfe_col = db.pick_first(work.columns, ["mfe_price", "mfe"])
    mae_col = db.pick_first(work.columns, ["mae_price", "mae"])
    if side_col and entry_col and mfe_col and mae_col:
        side = work[side_col].astype(str).str.upper()
        entry = _safe_numeric(work, entry_col)
        mfe = _safe_numeric(work, mfe_col)
        mae = _safe_numeric(work, mae_col)
        denom = (mfe - mae).replace(0, np.nan)
        eff = np.where(side.str.contains("SHORT"), (mfe - entry) / denom, (entry - mae) / denom)
        work["entry_efficiency"] = pd.Series(eff).clip(0, 1)
        plt.figure(figsize=(8, 4))
        sns.histplot(work["entry_efficiency"].dropna(), bins=30, kde=True)
        plt.title("Entry Efficiency")
        plt.tight_layout()
        plt.savefig(out["charts"] / "entry_efficiency.png")
        plt.close()
    else:
        skipped.append("entry_efficiency")
        log.warning("missing columns for entry efficiency")

    mid_col = db.pick_first(work.columns, ["midprice", "mid_price", "mark_price"])
    if entry_col and mid_col:
        work["entry_price"] = _safe_numeric(work, entry_col)
        work["mid_price"] = _safe_numeric(work, mid_col)
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="mid_price", y="entry_price", alpha=0.45)
        plt.title("Entry vs Midprice")
        plt.tight_layout()
        plt.savefig(out["charts"] / "entry_vs_midprice.png")
        plt.close()
    else:
        skipped.append("entry_vs_midprice")
        log.warning("missing entry/midprice columns")

    # Execution charts
    delay_col = db.pick_first(work.columns, ["entry_delay_ms", "entry_delay", "signal_age_ms"])
    if delay_col:
        work["entry_delay"] = _safe_numeric(work, delay_col)
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="entry_delay", y="pnl", alpha=0.45)
        plt.title("Entry Delay vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "entry_delay_vs_pnl.png")
        plt.close()
    else:
        skipped.append("entry_delay_vs_pnl")
        log.warning("missing entry delay column")

    latency_col = db.pick_first(work.columns, ["latency_ms", "latency", "exec_latency_ms"])
    if latency_col:
        work["latency"] = _safe_numeric(work, latency_col)
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="latency", y="pnl", alpha=0.45)
        plt.title("Latency vs PnL")
        plt.tight_layout()
        plt.savefig(out["charts"] / "latency_vs_pnl.png")
        plt.close()
    else:
        skipped.append("latency_vs_pnl")
        log.warning("missing latency column")

    slippage_col = db.pick_first(work.columns, ["slippage", "slippage_bps", "entry_slippage"])
    if slippage_col:
        work["slippage"] = _safe_numeric(work, slippage_col)
        plt.figure(figsize=(8, 4))
        sns.histplot(work["slippage"].dropna(), bins=30, kde=True)
        plt.title("Slippage Distribution")
        plt.tight_layout()
        plt.savefig(out["charts"] / "slippage_distribution.png")
        plt.close()
    else:
        skipped.append("slippage_distribution")
        log.warning("missing slippage column")

    # Profit capture charts
    mfe_col = db.pick_first(work.columns, ["mfe", "mfe_price"])
    mae_col = db.pick_first(work.columns, ["mae", "mae_price"])
    if mfe_col:
        work["mfe"] = _safe_numeric(work, mfe_col)
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="mfe", y="pnl", alpha=0.45)
        plt.title("PnL vs MFE")
        plt.tight_layout()
        plt.savefig(out["charts"] / "pnl_vs_mfe.png")
        plt.close()

        plt.figure(figsize=(8, 4))
        sns.histplot(work["mfe"].dropna(), bins=30, kde=True)
        plt.title("MFE Distribution")
        plt.tight_layout()
        plt.savefig(out["charts"] / "mfe_distribution.png")
        plt.close()
    else:
        skipped.extend(["pnl_vs_mfe", "mfe_distribution"])
        log.warning("missing MFE column")

    if mae_col:
        work["mae"] = _safe_numeric(work, mae_col)
        plt.figure(figsize=(8, 4))
        sns.scatterplot(data=work, x="mae", y="pnl", alpha=0.45)
        plt.title("PnL vs MAE")
        plt.tight_layout()
        plt.savefig(out["charts"] / "pnl_vs_mae.png")
        plt.close()

        plt.figure(figsize=(8, 4))
        sns.histplot(work["mae"].dropna(), bins=30, kde=True)
        plt.title("MAE Distribution")
        plt.tight_layout()
        plt.savefig(out["charts"] / "mae_distribution.png")
        plt.close()
    else:
        skipped.extend(["pnl_vs_mae", "mae_distribution"])
        log.warning("missing MAE column")

    if mfe_col and mae_col:
        denom = work["mfe"].abs().replace(0, np.nan)
        work["profit_capture_ratio"] = work["pnl"] / denom
        plt.figure(figsize=(8, 4))
        sns.histplot(work["profit_capture_ratio"].dropna(), bins=30, kde=True)
        plt.title("Profit Capture Ratio")
        plt.tight_layout()
        plt.savefig(out["charts"] / "profit_capture_ratio.png")
        plt.close()
    else:
        skipped.append("profit_capture_ratio")
        log.warning("missing MFE/MAE columns for capture ratio")

    keep = [c for c in ["pnl", "score", "entry_distance", "entry_efficiency", "entry_delay", "latency", "slippage", "mfe", "mae", "profit_capture_ratio"] if c in work.columns]
    if keep:
        work[keep].to_csv(out["csv"] / "signal_edge_analysis.csv", index=False)
    return {"status": "ok", "rows": int(work["pnl"].notna().sum()), "table": table, "skipped_graphs": skipped}
