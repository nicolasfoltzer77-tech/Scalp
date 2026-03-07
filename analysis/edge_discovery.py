from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

from analysis import db


REQUIRED_COLUMNS = [
    "instId",
    "pnl_net",
    "score_C",
    "score_S",
    "score_H",
    "lev",
    "volatility",
    "ts_open",
]


def _quantile_bucket(series: pd.Series, q: int = 5, prefix: str = "Q") -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    if clean.notna().sum() < 2:
        return pd.Series([pd.NA] * len(series), index=series.index, dtype="object")
    try:
        binned = pd.qcut(clean, q=min(q, clean.notna().nunique()), duplicates="drop")
    except ValueError:
        binned = pd.cut(clean, bins=min(q, clean.notna().nunique()))
    if not hasattr(binned, "cat"):
        return binned.astype("object")

    labels = []
    for idx, interval in enumerate(binned.cat.categories, start=1):
        labels.append(f"{prefix}{idx}: {interval.left:.4g}..{interval.right:.4g}")
    mapper = dict(zip(binned.cat.categories, labels))
    return binned.map(mapper)


def _compute_metrics(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, sub in df.groupby(group_cols, dropna=False, observed=False):
        pnl = pd.to_numeric(sub["pnl_net"], errors="coerce").dropna()
        if pnl.empty:
            continue
        gross_profit = float(pnl[pnl > 0].sum())
        gross_loss_abs = float(abs(pnl[pnl < 0].sum()))
        if gross_loss_abs == 0 and gross_profit > 0:
            pf = float(np.inf)
        elif gross_loss_abs == 0:
            pf = np.nan
        else:
            pf = gross_profit / gross_loss_abs

        rec = {
            "expectancy": float(pnl.mean()),
            "profit_factor": float(pf) if pd.notna(pf) else np.nan,
            "winrate": float((pnl > 0).mean()),
            "trade_count": int(len(pnl)),
        }
        if not isinstance(keys, tuple):
            keys = (keys,)
        for col, value in zip(group_cols, keys):
            rec[col] = value
        rows.append(rec)

    out_cols = group_cols + ["expectancy", "profit_factor", "winrate", "trade_count"]
    return pd.DataFrame(rows, columns=out_cols)


def _save_heatmap(metrics: pd.DataFrame, x_col: str, y_col: str, value_col: str, out_path: Path, title: str) -> bool:
    if metrics.empty:
        return False
    pivot = metrics.pivot(index=y_col, columns=x_col, values=value_col)
    if pivot.empty:
        return False

    plt.figure(figsize=(1.6 * max(3, len(pivot.columns)), 1.2 * max(3, len(pivot.index))))
    img = plt.imshow(pivot.values, aspect="auto", cmap="RdYlGn")
    plt.xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns], rotation=45, ha="right")
    plt.yticks(range(len(pivot.index)), [str(i) for i in pivot.index])
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    plt.title(title)
    cbar = plt.colorbar(img)
    cbar.set_label(value_col)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    return True


def _save_sorted_bar(metrics: pd.DataFrame, label_col: str, value_col: str, out_path: Path, title: str) -> bool:
    if metrics.empty:
        return False
    data = metrics[[label_col, value_col]].dropna().sort_values(value_col, ascending=False).head(20)
    if data.empty:
        return False
    plt.figure(figsize=(12, 6))
    plt.bar(data[label_col].astype(str), data[value_col])
    plt.xticks(rotation=45, ha="right")
    plt.title(title)
    plt.ylabel(value_col)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    return True


def _feature_predictive_power(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    y = pd.to_numeric(df["pnl_net"], errors="coerce")
    total_var = float(y.var())
    rows = []
    for col in feature_cols:
        sub = df[[col, "pnl_net"]].dropna()
        if sub.empty:
            continue
        grouped = sub.groupby(col, observed=False)["pnl_net"].agg(["mean", "count"])
        if grouped.empty:
            continue
        global_mean = float(sub["pnl_net"].mean())
        between_var = float(((grouped["mean"] - global_mean) ** 2 * grouped["count"]).sum() / max(1, grouped["count"].sum()))
        score = between_var / total_var if total_var and np.isfinite(total_var) and total_var > 0 else np.nan
        rows.append({"feature": col, "predictive_score": score})
    return pd.DataFrame(rows).sort_values("predictive_score", ascending=False)


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in trades.columns]
    if missing_cols:
        return {"status": "skipped", "reason": "missing required columns", "missing": missing_cols, "table": table}

    work = trades[REQUIRED_COLUMNS].copy()
    work["pnl_net"] = pd.to_numeric(work["pnl_net"], errors="coerce")
    work["ts_open"] = db.to_datetime_series(work["ts_open"])
    work = work.dropna(subset=["pnl_net", "ts_open"])
    if work.empty:
        return {"status": "skipped", "reason": "no valid rows after cleanup", "table": table}

    work["coin"] = work["instId"].astype(str)
    work["hour_of_day"] = work["ts_open"].dt.hour
    work["volatility_bucket"] = _quantile_bucket(work["volatility"], q=5, prefix="V")
    work["leverage_bucket"] = _quantile_bucket(work["lev"], q=5, prefix="L")
    work["score_C_bucket"] = _quantile_bucket(work["score_C"], q=5, prefix="C")
    work["score_S_bucket"] = _quantile_bucket(work["score_S"], q=5, prefix="S")
    work["score_H_bucket"] = _quantile_bucket(work["score_H"], q=5, prefix="H")

    tables_dir = out["root"] / "tables"
    charts_dir = out["charts"]
    tables_dir.mkdir(parents=True, exist_ok=True)

    grouped_specs = {
        "coin": ["coin"],
        "hour_of_day": ["hour_of_day"],
        "volatility_bucket": ["volatility_bucket"],
        "score_C_bucket": ["score_C_bucket"],
        "score_S_bucket": ["score_S_bucket"],
        "score_H_bucket": ["score_H_bucket"],
        "leverage_bucket": ["leverage_bucket"],
    }

    output_tables: list[str] = []
    all_single_regimes: list[pd.DataFrame] = []
    for name, cols in grouped_specs.items():
        metrics = _compute_metrics(work, cols).sort_values("expectancy", ascending=False)
        if metrics.empty:
            continue
        metrics.insert(0, "regime_type", name)
        metrics.insert(1, "regime", metrics[cols].astype(str).agg(" | ".join, axis=1))
        all_single_regimes.append(metrics[["regime_type", "regime", "expectancy", "profit_factor", "winrate", "trade_count"]])
        csv_path = tables_dir / f"edge_discovery_by_{name}.csv"
        metrics.to_csv(csv_path, index=False)
        output_tables.append(str(csv_path.relative_to(out["root"])))

    cross_specs = {
        "coin_vs_hour_of_day": ["coin", "hour_of_day"],
        "volatility_vs_score_C": ["volatility_bucket", "score_C_bucket"],
        "leverage_vs_volatility": ["leverage_bucket", "volatility_bucket"],
    }
    cross_metrics: dict[str, pd.DataFrame] = {}
    for name, cols in cross_specs.items():
        metrics = _compute_metrics(work, cols).sort_values("expectancy", ascending=False)
        if metrics.empty:
            continue
        cross_metrics[name] = metrics
        csv_path = tables_dir / f"edge_discovery_{name}.csv"
        metrics.to_csv(csv_path, index=False)
        output_tables.append(str(csv_path.relative_to(out["root"])))

    charts_written: list[str] = []
    if "coin_vs_hour_of_day" in cross_metrics and _save_heatmap(
        cross_metrics["coin_vs_hour_of_day"],
        x_col="hour_of_day",
        y_col="coin",
        value_col="expectancy",
        out_path=charts_dir / "edge_matrix_heatmap.png",
        title="Edge Matrix: Expectancy by Coin vs Hour of Day",
    ):
        charts_written.append("graphs/edge_matrix_heatmap.png")

    if "coin_vs_hour_of_day" in cross_metrics and _save_heatmap(
        cross_metrics["coin_vs_hour_of_day"],
        x_col="hour_of_day",
        y_col="coin",
        value_col="expectancy",
        out_path=charts_dir / "expectancy_by_coin_hour.png",
        title="Expectancy by Coin and Hour",
    ):
        charts_written.append("graphs/expectancy_by_coin_hour.png")

    if "volatility_vs_score_C" in cross_metrics and _save_heatmap(
        cross_metrics["volatility_vs_score_C"],
        x_col="score_C_bucket",
        y_col="volatility_bucket",
        value_col="expectancy",
        out_path=charts_dir / "expectancy_by_volatility_score.png",
        title="Expectancy by Volatility vs Score C",
    ):
        charts_written.append("graphs/expectancy_by_volatility_score.png")

    combined_regimes = pd.concat(all_single_regimes, ignore_index=True) if all_single_regimes else pd.DataFrame()
    regime_bar = combined_regimes.copy()
    if not regime_bar.empty:
        regime_bar["label"] = regime_bar["regime_type"] + ": " + regime_bar["regime"]
    if not regime_bar.empty and _save_sorted_bar(
        regime_bar,
        label_col="label",
        value_col="profit_factor",
        out_path=charts_dir / "profit_factor_by_regime.png",
        title="Top Profit Factor by Regime",
    ):
        charts_written.append("graphs/profit_factor_by_regime.png")

    feature_cols = [
        "coin",
        "hour_of_day",
        "volatility_bucket",
        "score_C_bucket",
        "score_S_bucket",
        "score_H_bucket",
        "leverage_bucket",
    ]
    fi = _feature_predictive_power(work, feature_cols)
    if not fi.empty:
        plt.figure(figsize=(10, 5))
        plt.bar(fi["feature"], fi["predictive_score"])
        plt.xticks(rotation=45, ha="right")
        plt.ylabel("predictive_score")
        plt.title("Feature Importance Rank")
        plt.tight_layout()
        fi_chart = charts_dir / "feature_importance_rank.png"
        plt.savefig(fi_chart)
        plt.close()
        fi_csv = tables_dir / "edge_discovery_feature_importance.csv"
        fi.to_csv(fi_csv, index=False)
        output_tables.append(str(fi_csv.relative_to(out["root"])))
        charts_written.append("graphs/feature_importance_rank.png")

    filtered = combined_regimes[combined_regimes["trade_count"] >= 5] if not combined_regimes.empty else pd.DataFrame()
    if filtered.empty:
        filtered = combined_regimes

    top_profitable = (
        filtered.sort_values("expectancy", ascending=False)
        .head(5)[["regime_type", "regime", "expectancy", "profit_factor", "winrate", "trade_count"]]
        .to_dict("records")
        if not filtered.empty
        else []
    )
    top_losing = (
        filtered.sort_values("expectancy", ascending=True)
        .head(5)[["regime_type", "regime", "expectancy", "profit_factor", "winrate", "trade_count"]]
        .to_dict("records")
        if not filtered.empty
        else []
    )
    most_predictive = fi.iloc[0].to_dict() if not fi.empty else None

    return {
        "status": "ok",
        "table": table,
        "rows": int(len(work)),
        "tables": output_tables,
        "charts": charts_written,
        "top_profitable_regimes": top_profitable,
        "top_losing_regimes": top_losing,
        "most_predictive_feature": most_predictive,
    }
