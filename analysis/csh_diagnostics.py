from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

from analysis import db

SCORE_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
SCORE_LABELS = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
SCORE_COMPONENTS = ["score_C", "score_S", "score_H"]
SIGNAL_COMPONENTS = ["s_struct", "s_timing", "s_quality", "s_vol", "s_confirm"]


def _save_hist(series: pd.Series, title: str, out_path: Path) -> None:
    plt.figure(figsize=(8, 4.5))
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        plt.hist(clean, bins=20, color="tab:blue", edgecolor="black", alpha=0.8)
        plt.xlabel("Score")
        plt.ylabel("Trade count")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _metric_frame(df: pd.DataFrame, group_col: str, pnl_col: str = "pnl_net") -> pd.DataFrame:
    if group_col not in df.columns or pnl_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "trade_count", "winrate", "expectancy", "profit_factor"])

    scoped = df[[group_col, pnl_col]].copy()
    scoped[pnl_col] = pd.to_numeric(scoped[pnl_col], errors="coerce")
    scoped = scoped.dropna(subset=[group_col, pnl_col])
    if scoped.empty:
        return pd.DataFrame(columns=[group_col, "trade_count", "winrate", "expectancy", "profit_factor"])

    rows: list[dict] = []
    for key, sub in scoped.groupby(group_col, observed=False):
        pnl = sub[pnl_col]
        profits = pnl[pnl > 0].sum()
        losses = pnl[pnl < 0].sum()
        pf = np.inf if losses == 0 and profits > 0 else (profits / abs(losses) if losses != 0 else np.nan)
        rows.append(
            {
                group_col: key,
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "profit_factor": float(pf) if pd.notna(pf) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _bucket_expectancy(work: pd.DataFrame, score_col: str) -> pd.DataFrame:
    if score_col not in work.columns:
        return pd.DataFrame(columns=["score_bucket", "trade_count", "winrate", "expectancy", "profit_factor"])

    scoped = work[[score_col, "pnl_net"]].copy()
    scoped[score_col] = pd.to_numeric(scoped[score_col], errors="coerce")
    scoped["score_bucket"] = pd.cut(
        scoped[score_col], bins=SCORE_BINS, labels=SCORE_LABELS, include_lowest=True, right=True
    )
    summary = _metric_frame(scoped.dropna(subset=["score_bucket"]), "score_bucket")
    order = {label: idx for idx, label in enumerate(SCORE_LABELS)}
    if not summary.empty:
        summary = summary.sort_values("score_bucket", key=lambda s: s.astype(str).map(order))
    return summary


def _plot_expectancy_bar(summary: pd.DataFrame, x_col: str, title: str, out_path: Path) -> None:
    plt.figure(figsize=(8, 4.5))
    if summary.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        x = summary[x_col].astype(str)
        y = summary["expectancy"]
        colors = ["tab:green" if val >= 0 else "tab:red" for val in y]
        plt.bar(x, y, color=colors)
        plt.axhline(0, color="black", linewidth=1)
        plt.xticks(rotation=15)
        plt.ylabel("Expectancy (avg pnl_net)")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def _score_distributions(work: pd.DataFrame, out: dict) -> dict:
    for score_col in SCORE_COMPONENTS:
        if score_col in work.columns:
            _save_hist(
                work[score_col],
                f"Distribution of {score_col}",
                out["charts"] / f"{score_col}_distribution.png",
            )
    return {"distributions": len([c for c in SCORE_COMPONENTS if c in work.columns])}


def _expectancy_vs_score(work: pd.DataFrame, out: dict) -> dict:
    rows = []
    for score_col in SCORE_COMPONENTS:
        summary = _bucket_expectancy(work, score_col)
        summary.insert(0, "score", score_col)
        summary.to_csv(out["csv"] / f"expectancy_vs_{score_col}.csv", index=False)
        _plot_expectancy_bar(
            summary,
            "score_bucket",
            f"Expectancy vs {score_col}",
            out["charts"] / f"expectancy_vs_{score_col}.png",
        )
        rows.append(summary)

    combined = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    combined.to_csv(out["csv"] / "csh_expectancy_by_score.csv", index=False)
    return {"score_bucket_rows": int(len(combined))}


def _signal_quality_analysis(work: pd.DataFrame, out: dict) -> dict:
    rows = []
    for component in SIGNAL_COMPONENTS:
        if component not in work.columns:
            continue
        scoped = work[[component, "pnl_net"]].copy()
        scoped[component] = pd.to_numeric(scoped[component], errors="coerce")
        scoped["active"] = scoped[component].fillna(0) > 0
        pnl = pd.to_numeric(scoped.loc[scoped["active"], "pnl_net"], errors="coerce").dropna()
        if pnl.empty:
            continue
        profits = pnl[pnl > 0].sum()
        losses = pnl[pnl < 0].sum()
        pf = np.inf if losses == 0 and profits > 0 else (profits / abs(losses) if losses != 0 else np.nan)
        rows.append(
            {
                "component": component,
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "profit_factor": float(pf) if pd.notna(pf) else np.nan,
            }
        )

    summary = pd.DataFrame(rows).sort_values("expectancy", ascending=False) if rows else pd.DataFrame(
        columns=["component", "trade_count", "winrate", "expectancy", "profit_factor"]
    )
    summary.to_csv(out["csv"] / "signal_component_edge.csv", index=False)

    _plot_expectancy_bar(summary, "component", "Expectancy by Signal Component", out["charts"] / "expectancy_by_signal_component.png")
    return {"signal_components": int(len(summary))}


def _context_edge(work: pd.DataFrame, out: dict) -> dict:
    if "score_C" not in work.columns:
        summary = pd.DataFrame(columns=["context", "trade_count", "winrate", "expectancy", "profit_factor"])
    else:
        scoped = work[["score_C", "pnl_net"]].copy()
        scoped["score_C"] = pd.to_numeric(scoped["score_C"], errors="coerce")
        scoped = scoped.dropna(subset=["score_C", "pnl_net"])
        scoped["context"] = np.where(scoped["score_C"] >= 0, "bullish", "bearish")
        summary = _metric_frame(scoped, "context")

    summary.to_csv(out["csv"] / "context_edge.csv", index=False)
    _plot_expectancy_bar(summary, "context", "Expectancy by Context Sign", out["charts"] / "expectancy_by_context.png")
    return {"contexts": int(len(summary))}


def _sizing_validation(work: pd.DataFrame, out: dict) -> dict:
    required = set(SCORE_COMPONENTS + ["pnl_net"])
    if not required.issubset(work.columns):
        pd.DataFrame().to_csv(out["csv"] / "sizing_validation.csv", index=False)
        _plot_expectancy_bar(
            pd.DataFrame(columns=["size_bucket", "expectancy"]),
            "size_bucket",
            "Expectancy by Size Model Bucket",
            out["charts"] / "size_bucket_expectancy.png",
        )
        plt.figure(figsize=(7, 5))
        plt.text(0.5, 0.5, "Missing score columns", ha="center", va="center")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out["charts"] / "size_vs_pnl_scatter.png")
        plt.close()
        return {"sizing_rows": 0}

    scoped = work[["score_C", "score_S", "score_H", "pnl_net"]].copy()
    for col in ["score_C", "score_S", "score_H", "pnl_net"]:
        scoped[col] = pd.to_numeric(scoped[col], errors="coerce")
    scoped = scoped.dropna()

    scoped["size_model"] = ((scoped["score_C"].abs() + scoped["score_S"]) / 2.0) * (0.5 + scoped["score_H"])
    scoped.to_csv(out["csv"] / "sizing_validation.csv", index=False)

    corr = float(scoped[["size_model", "pnl_net"]].corr().iloc[0, 1]) if len(scoped) > 1 else np.nan

    plt.figure(figsize=(7, 5))
    if scoped.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        plt.scatter(scoped["size_model"], scoped["pnl_net"], alpha=0.4, s=12)
        plt.axhline(0, color="black", linewidth=1)
        plt.xlabel("size_model")
        plt.ylabel("pnl_net")
        plt.title(f"size_model vs pnl_net (corr={corr:.3f})" if pd.notna(corr) else "size_model vs pnl_net")
    plt.tight_layout()
    plt.savefig(out["charts"] / "size_vs_pnl_scatter.png")
    plt.close()

    scoped["size_bucket"] = pd.qcut(scoped["size_model"], q=5, duplicates="drop") if not scoped.empty else pd.Series(dtype=object)
    bucket_summary = _metric_frame(scoped.dropna(subset=["size_bucket"]), "size_bucket")
    if not bucket_summary.empty:
        bucket_summary["size_bucket"] = bucket_summary["size_bucket"].astype(str)
    bucket_summary.to_csv(out["csv"] / "size_bucket_expectancy.csv", index=False)
    _plot_expectancy_bar(
        bucket_summary,
        "size_bucket",
        "Expectancy by Size Model Bucket",
        out["charts"] / "size_bucket_expectancy.png",
    )

    return {"sizing_rows": int(len(scoped)), "size_pnl_corr": corr}


def _score_surface(work: pd.DataFrame, out: dict) -> dict:
    needed = {"score_C", "score_S", "pnl_net"}
    if not needed.issubset(work.columns):
        pd.DataFrame().to_csv(out["csv"] / "expectancy_surface_C_S.csv", index=False)
        plt.figure(figsize=(7, 5))
        plt.text(0.5, 0.5, "Missing score_C/score_S", ha="center", va="center")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out["charts"] / "expectancy_surface_C_S.png")
        plt.close()
        return {"surface_cells": 0}

    scoped = work[["score_C", "score_S", "pnl_net"]].copy()
    for col in needed:
        scoped[col] = pd.to_numeric(scoped[col], errors="coerce")
    scoped = scoped.dropna()
    if scoped.empty:
        surface = pd.DataFrame()
    else:
        scoped["C_bucket"] = pd.cut(scoped["score_C"].abs(), bins=SCORE_BINS, labels=SCORE_LABELS, include_lowest=True)
        scoped["S_bucket"] = pd.cut(scoped["score_S"], bins=SCORE_BINS, labels=SCORE_LABELS, include_lowest=True)
        surface = (
            scoped.dropna(subset=["C_bucket", "S_bucket"]).groupby(["C_bucket", "S_bucket"], observed=False)["pnl_net"].mean().reset_index(name="expectancy")
        )

    surface.to_csv(out["csv"] / "expectancy_surface_C_S.csv", index=False)

    plt.figure(figsize=(8, 6))
    if surface.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        pivot = surface.pivot(index="C_bucket", columns="S_bucket", values="expectancy")
        im = plt.imshow(pivot.values, cmap="RdYlGn", aspect="auto")
        plt.colorbar(im, label="Expectancy")
        plt.xticks(range(len(pivot.columns)), [str(c) for c in pivot.columns], rotation=45)
        plt.yticks(range(len(pivot.index)), [str(i) for i in pivot.index])
        plt.xlabel("score_S bucket")
        plt.ylabel("|score_C| bucket")
    plt.title("Expectancy Surface: score_C vs score_S")
    plt.tight_layout()
    plt.savefig(out["charts"] / "expectancy_surface_C_S.png")
    plt.close()

    return {"surface_cells": int(len(surface))}


def _time_delta_seconds(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().empty:
        return numeric
    if numeric.notna().mean() > 0.8 and numeric.dropna().median() > 1e10:
        return numeric / 1000.0
    return numeric


def _edge_decay(work: pd.DataFrame, out: dict) -> dict:
    candidates = [
        ("time_to_mfe", "time_to_mae"),
        ("t_mfe", "t_mae"),
    ]
    chosen = None
    for mfe_col, mae_col in candidates:
        if mfe_col in work.columns and mae_col in work.columns:
            chosen = (mfe_col, mae_col)
            break

    if not chosen and {"ts_open", "ts_mfe", "ts_mae"}.issubset(work.columns):
        scoped = work[["ts_open", "ts_mfe", "ts_mae", "score_S", "pnl_net"]].copy()
        for col in ["ts_open", "ts_mfe", "ts_mae"]:
            scoped[col] = _time_delta_seconds(scoped[col])
        scoped["time_to_MFE"] = scoped["ts_mfe"] - scoped["ts_open"]
        scoped["time_to_MAE"] = scoped["ts_mae"] - scoped["ts_open"]
    elif chosen:
        mfe_col, mae_col = chosen
        scoped = work[[mfe_col, mae_col, "score_S", "pnl_net"]].copy()
        scoped["time_to_MFE"] = _time_delta_seconds(scoped[mfe_col])
        scoped["time_to_MAE"] = _time_delta_seconds(scoped[mae_col])
    else:
        pd.DataFrame().to_csv(out["csv"] / "edge_decay_times.csv", index=False)
        plt.figure(figsize=(7, 5))
        plt.text(0.5, 0.5, "No time_to_MFE/MAE data", ha="center", va="center")
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(out["charts"] / "time_to_mfe_vs_score_S.png")
        plt.close()
        return {"edge_decay_rows": 0}

    scoped["score_S"] = pd.to_numeric(scoped["score_S"], errors="coerce")
    scoped["pnl_net"] = pd.to_numeric(scoped["pnl_net"], errors="coerce")
    scoped = scoped.dropna(subset=["time_to_MFE", "time_to_MAE", "score_S", "pnl_net"])
    scoped = scoped[(scoped["time_to_MFE"] >= 0) & (scoped["time_to_MAE"] >= 0)]

    scoped.to_csv(out["csv"] / "edge_decay_times.csv", index=False)

    plt.figure(figsize=(7, 5))
    if scoped.empty:
        plt.text(0.5, 0.5, "No data", ha="center", va="center")
        plt.axis("off")
    else:
        plt.scatter(scoped["score_S"], scoped["time_to_MFE"], alpha=0.35, s=12)
        plt.xlabel("score_S")
        plt.ylabel("time_to_MFE (s)")
    plt.title("time_to_MFE vs score_S")
    plt.tight_layout()
    plt.savefig(out["charts"] / "time_to_mfe_vs_score_S.png")
    plt.close()

    return {"edge_decay_rows": int(len(scoped))}


def _summary_report(out: dict) -> dict:
    def _safe_read(path: Path) -> pd.DataFrame:
        return pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame()

    score_df = _safe_read(out["csv"] / "csh_expectancy_by_score.csv")
    signal_df = _safe_read(out["csv"] / "signal_component_edge.csv")
    size_df = _safe_read(out["csv"] / "size_bucket_expectancy.csv")

    best_score_ranges: list[dict] = []
    worst_score_ranges: list[dict] = []
    if not score_df.empty and "expectancy" in score_df.columns:
        sorted_scores = score_df.sort_values("expectancy", ascending=False)
        best_score_ranges = sorted_scores.head(5).to_dict(orient="records")
        worst_score_ranges = sorted_scores.tail(5).sort_values("expectancy", ascending=True).to_dict(orient="records")

    best_signal_components = (
        signal_df.sort_values("expectancy", ascending=False).head(5).to_dict(orient="records")
        if not signal_df.empty and "expectancy" in signal_df.columns
        else []
    )

    sizing_validation_result: dict[str, object] = {"status": "insufficient_data"}
    if not size_df.empty and "expectancy" in size_df.columns:
        monotonic = bool(size_df["expectancy"].is_monotonic_increasing)
        sizing_validation_result = {
            "status": "ok",
            "bucket_count": int(len(size_df)),
            "expectancy_monotonic_increasing": monotonic,
            "max_bucket_expectancy": float(size_df["expectancy"].max()),
            "min_bucket_expectancy": float(size_df["expectancy"].min()),
        }

    report = {
        "best_score_ranges": best_score_ranges,
        "worst_score_ranges": worst_score_ranges,
        "best_signal_components": best_signal_components,
        "sizing_validation_result": sizing_validation_result,
    }

    report_path = out["reports"] / "csh_diagnostics.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    if trades is None:
        return {"status": "skipped", "reason": "trades table not found"}

    needed = [
        "uid",
        "instId",
        "side",
        "pnl_net",
        "entry",
        "lev",
        "score_C",
        "score_S",
        "score_H",
        "s_struct",
        "s_timing",
        "s_quality",
        "s_vol",
        "s_confirm",
        "ts_open",
        "ts_close",
    ]
    available = [c for c in needed if c in trades.columns]
    if "pnl_net" not in available:
        pnl_col = db.find_pnl_col(trades.columns)
        if pnl_col:
            available.append(pnl_col)
            trades = trades.rename(columns={pnl_col: "pnl_net"})

    work = trades[available].copy() if available else trades.copy()
    work["pnl_net"] = pd.to_numeric(work.get("pnl_net"), errors="coerce")
    work = work.dropna(subset=["pnl_net"])

    result = {"status": "ok", "table": table, "rows": int(len(work)), "columns_used": available}
    result.update(_score_distributions(work, out))
    result.update(_expectancy_vs_score(work, out))
    result.update(_signal_quality_analysis(work, out))
    result.update(_context_edge(work, out))
    result.update(_sizing_validation(work, out))
    result.update(_score_surface(work, out))
    result.update(_edge_decay(work, out))
    summary = _summary_report(out)
    result["summary_report"] = summary
    return result


if __name__ == "__main__":
    output = db.ensure_output_dirs("analysis_output")
    with db.connect_db() as connection:
        print(run(connection, output))
