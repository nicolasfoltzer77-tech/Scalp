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


SCORE_CANDIDATES = [
    "gest_score",
    "entry_score",
    "score",
    "signal_score",
    "quality_score",
]
VOLATILITY_CANDIDATES = [
    "volatility_bucket",
    "volatility_regime",
    "atr_signal",
    "atr",
    "realized_volatility",
    "volatility",
]
SIZE_CANDIDATES = [
    "position_size",
    "size",
    "qty",
    "quantity",
    "contracts",
    "sz",
    "notional",
    "notional_usd",
]


def _bucket_numeric(series: pd.Series, prefix: str, buckets: int = 5) -> pd.Series:
    clean = pd.to_numeric(series, errors="coerce")
    if clean.notna().sum() < buckets:
        return pd.Series([pd.NA] * len(clean), index=clean.index, dtype="object")

    try:
        binned = pd.qcut(clean, q=buckets, duplicates="drop")
    except ValueError:
        binned = pd.cut(clean, bins=buckets)

    labels = []
    for idx, interval in enumerate(binned.cat.categories, start=1):
        labels.append(f"{prefix}{idx}: {interval.left:.4g}..{interval.right:.4g}")
    mapper = {k: v for k, v in zip(binned.cat.categories, labels)}
    return binned.map(mapper)


def _compute_edge_metrics(df: pd.DataFrame, pnl_col: str, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, sub in df.groupby(group_cols, dropna=False, observed=False):
        pnl = pd.to_numeric(sub[pnl_col], errors="coerce").dropna()
        if pnl.empty:
            continue

        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        gross_profit = float(wins.sum())
        gross_loss_abs = float(abs(losses.sum()))

        if gross_loss_abs == 0 and gross_profit > 0:
            profit_factor = float(np.inf)
        elif gross_loss_abs == 0:
            profit_factor = np.nan
        else:
            profit_factor = gross_profit / gross_loss_abs

        rec = {
            "trades": int(len(pnl)),
            "expectancy": float(pnl.mean()),
            "profit_factor": float(profit_factor) if pd.notna(profit_factor) else np.nan,
            "winrate": float((pnl > 0).mean()),
            "avg_win": float(wins.mean()) if not wins.empty else 0.0,
            "avg_loss": float(losses.mean()) if not losses.empty else 0.0,
            "gross_profit": gross_profit,
            "gross_loss_abs": gross_loss_abs,
        }

        if not isinstance(keys, tuple):
            keys = (keys,)
        for c, v in zip(group_cols, keys):
            rec[c] = v
        rows.append(rec)

    cols = group_cols + [
        "trades",
        "expectancy",
        "profit_factor",
        "winrate",
        "avg_win",
        "avg_loss",
        "gross_profit",
        "gross_loss_abs",
    ]
    return pd.DataFrame(rows, columns=cols)


def _save_heatmap(metrics: pd.DataFrame, x_col: str, y_col: str, value_col: str, out_path: Path, title: str) -> bool:
    if metrics.empty or value_col not in metrics.columns:
        return False

    data = metrics[[y_col, x_col, value_col]].dropna(subset=[y_col, x_col])
    if data.empty:
        return False

    pivot = data.pivot(index=y_col, columns=x_col, values=value_col)
    if pivot.empty:
        return False

    plt.figure(figsize=(1.8 * max(3, len(pivot.columns)), 1.2 * max(3, len(pivot.index))))
    img = plt.imshow(pivot.values, aspect="auto", cmap="RdYlGn")
    plt.xticks(ticks=range(len(pivot.columns)), labels=[str(c) for c in pivot.columns], rotation=45, ha="right")
    plt.yticks(ticks=range(len(pivot.index)), labels=[str(i) for i in pivot.index])
    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel(y_col)
    cbar = plt.colorbar(img)
    cbar.set_label(value_col)

    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            if pd.notna(val):
                plt.text(j, i, f"{val:.3g}", ha="center", va="center", fontsize=8, color="black")

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
    work[pnl_col] = pd.to_numeric(work[pnl_col], errors="coerce")
    work = work.dropna(subset=[pnl_col])
    if work.empty:
        return {"status": "skipped", "reason": "no valid pnl rows", "table": table}

    score_col = db.pick_first(work.columns, SCORE_CANDIDATES)
    vol_col = db.pick_first(work.columns, VOLATILITY_CANDIDATES)
    size_col = db.pick_first(work.columns, SIZE_CANDIDATES)
    coin_col = db.find_symbol_col(work.columns)
    open_col, close_col = db.find_open_close_time_cols(work.columns)

    dims: dict[str, str] = {}

    if score_col:
        work["score_bucket"] = _bucket_numeric(work[score_col], prefix="S")
        if work["score_bucket"].notna().any():
            dims["score_bucket"] = "score_bucket"

    if vol_col:
        vol_numeric = pd.to_numeric(work[vol_col], errors="coerce")
        if vol_numeric.notna().mean() > 0.7:
            work["volatility_bucket"] = _bucket_numeric(work[vol_col], prefix="V")
        else:
            work["volatility_bucket"] = work[vol_col].astype(str)
        if work["volatility_bucket"].notna().any():
            dims["volatility_bucket"] = "volatility_bucket"

    time_col = open_col or close_col
    if time_col:
        ts = db.to_datetime_series(work[time_col])
        hour = ts.dt.hour
        time_bucket = pd.cut(
            hour,
            bins=[-1, 5, 11, 17, 23],
            labels=["overnight_utc", "morning_utc", "afternoon_utc", "evening_utc"],
        )
        work["time_of_day"] = time_bucket
        if work["time_of_day"].notna().any():
            dims["time_of_day"] = "time_of_day"

    if size_col:
        work["position_size_bucket"] = _bucket_numeric(work[size_col], prefix="P")
        if work["position_size_bucket"].notna().any():
            dims["position_size"] = "position_size_bucket"

    if coin_col:
        work["coin"] = work[coin_col].astype(str)
        work = work[work["coin"].str.len() > 0]
        if work["coin"].notna().any():
            dims["coin"] = "coin"

    if not dims:
        return {
            "status": "skipped",
            "reason": "no dimensions available for score/volatility/time/size/coin",
            "table": table,
        }

    table_outputs = []
    for name, col in dims.items():
        metrics = _compute_edge_metrics(work, pnl_col, [col]).sort_values("expectancy", ascending=False)
        if metrics.empty:
            continue
        csv_path = out["csv"] / f"edge_diagnostics_by_{name}.csv"
        metrics.to_csv(csv_path, index=False)
        table_outputs.append(csv_path.name)

    heatmaps = []
    if "score_bucket" in dims and "volatility_bucket" in dims:
        pair_metrics = _compute_edge_metrics(work, pnl_col, ["score_bucket", "volatility_bucket"])
        if not pair_metrics.empty:
            pair_csv = out["csv"] / "edge_diagnostics_score_vs_volatility.csv"
            pair_metrics.to_csv(pair_csv, index=False)
            table_outputs.append(pair_csv.name)

            for metric in ["expectancy", "profit_factor", "winrate", "avg_win", "avg_loss"]:
                chart_path = out["charts"] / f"edge_heatmap_score_vs_volatility_{metric}.png"
                ok = _save_heatmap(
                    pair_metrics,
                    x_col="volatility_bucket",
                    y_col="score_bucket",
                    value_col=metric,
                    out_path=chart_path,
                    title=f"{metric} by Score vs Volatility",
                )
                if ok:
                    heatmaps.append(chart_path.name)

    if "time_of_day" in dims and "coin" in dims:
        tcoin = _compute_edge_metrics(work, pnl_col, ["time_of_day", "coin"])
        if not tcoin.empty:
            tcoin_csv = out["csv"] / "edge_diagnostics_time_of_day_vs_coin.csv"
            tcoin.to_csv(tcoin_csv, index=False)
            table_outputs.append(tcoin_csv.name)
            chart_path = out["charts"] / "edge_heatmap_time_of_day_vs_coin_expectancy.png"
            if _save_heatmap(
                tcoin,
                x_col="coin",
                y_col="time_of_day",
                value_col="expectancy",
                out_path=chart_path,
                title="Expectancy by Time of Day vs Coin",
            ):
                heatmaps.append(chart_path.name)

    return {
        "status": "ok",
        "rows": int(len(work)),
        "table": table,
        "dimensions": dims,
        "tables": table_outputs,
        "heatmaps": heatmaps,
    }
