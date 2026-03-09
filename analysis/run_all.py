from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import sqlite3

import numpy as np
import pandas as pd

from analysis import db
from analysis import mfe_mae, expectancy, pyramiding, exit_reasons, leverage_analysis
from analysis import coin_analysis, time_analysis, equity_curve, edge_decay, clustering
from analysis import entry_efficiency, step_analysis, move_vs_fees, volatility_analysis, trade_clustering
from analysis import range_analysis, atr_analysis, signal_quality, duration_analysis, dashboard
from analysis import profit_capture, timing_analysis, entry_timing, entry_delay_analysis, volatility_edge
from analysis import entry_quality, latency_analysis
from analysis import performance_analysis, risk_analysis, signal_edge_analysis
from analysis import regime_analysis, time_analysis_extended, position_sizing_analysis, strategy_stability_analysis
from analysis import entry_decision_diagnostics, entry_pipeline_analysis, csh_diagnostics
from analysis import edge_diagnostics, edge_discovery


MODULES = [
    ("performance_analysis", performance_analysis.run),
    ("risk_analysis", risk_analysis.run),
    ("signal_edge_analysis", signal_edge_analysis.run),
    ("regime_analysis", regime_analysis.run),
    ("time_analysis_extended", time_analysis_extended.run),
    ("position_sizing_analysis", position_sizing_analysis.run),
    ("strategy_stability_analysis", strategy_stability_analysis.run),
    ("mfe_mae", mfe_mae.run),
    ("expectancy", expectancy.run),
    ("leverage_analysis", leverage_analysis.run),
    ("pyramiding", pyramiding.run),
    ("exit_reasons", exit_reasons.run),
    ("time_analysis", time_analysis.run),
    ("coin_analysis", coin_analysis.run),
    ("equity_curve", equity_curve.run),
    ("edge_decay", edge_decay.run),
    ("clustering", clustering.run),
    ("entry_efficiency", entry_efficiency.run),
    ("entry_quality", entry_quality.run),
    ("profit_capture", profit_capture.run),
    ("timing_analysis", timing_analysis.run),
    ("entry_timing", entry_timing.run),
    ("entry_delay_analysis", entry_delay_analysis.run),
    ("latency_analysis", latency_analysis.run),
    ("volatility_edge", volatility_edge.run),
    ("atr_analysis", atr_analysis.run),
    ("signal_quality", signal_quality.run),
    ("duration_analysis", duration_analysis.run),
    ("step_analysis", step_analysis.run),
    ("move_vs_fees", move_vs_fees.run),
    ("volatility_analysis", volatility_analysis.run),
    ("trade_clustering", trade_clustering.run),
    ("range_analysis", range_analysis.run),
    ("entry_decision_diagnostics", entry_decision_diagnostics.run),
    ("entry_pipeline_analysis", entry_pipeline_analysis.run),
    ("csh_diagnostics", csh_diagnostics.run),
    ("edge_diagnostics", edge_diagnostics.run),
    ("edge_discovery", edge_discovery.run),
]

STANDARD_METRIC_COLUMNS = [
    "trade_count",
    "winrate",
    "expectancy",
    "profit_factor",
    "avg_win",
    "avg_loss",
    "avg_duration",
]


def _standard_metrics_frame(pnl: pd.Series, duration_minutes: pd.Series | None = None) -> pd.DataFrame:
    pnl = pd.to_numeric(pnl, errors="coerce").dropna()
    if pnl.empty:
        return pd.DataFrame([{c: np.nan for c in STANDARD_METRIC_COLUMNS}])

    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]
    gross_profit = float(winners.sum())
    gross_loss_abs = float(abs(losers.sum()))
    if gross_loss_abs == 0 and gross_profit > 0:
        pf = np.inf
    elif gross_loss_abs == 0:
        pf = np.nan
    else:
        pf = gross_profit / gross_loss_abs

    avg_duration = np.nan
    if duration_minutes is not None:
        avg_duration = float(pd.to_numeric(duration_minutes, errors="coerce").dropna().mean())

    return pd.DataFrame(
        [
            {
                "trade_count": int(len(pnl)),
                "winrate": float((pnl > 0).mean()),
                "expectancy": float(pnl.mean()),
                "profit_factor": float(pf) if pd.notna(pf) else np.nan,
                "avg_win": float(winners.mean()) if not winners.empty else np.nan,
                "avg_loss": float(losers.mean()) if not losers.empty else np.nan,
                "avg_duration": avg_duration,
            }
        ]
    )


def _write_trade_summary(conn: sqlite3.Connection, out: dict) -> dict:
    trades, table = db.load_first_table(conn, ["recorder", "recorder_trades"])
    out_path = out["tables"] / "trade_summary.csv"
    if trades is None:
        pd.DataFrame(columns=STANDARD_METRIC_COLUMNS).to_csv(out_path, index=False)
        return {
            "trade_count_total": 0,
            "trade_count_used": 0,
            "columns_used": [],
            "missing_columns": ["trades_table"],
            "generated_tables": ["tables/trade_summary.csv"],
            "table": None,
        }

    pnl_col = db.find_pnl_col(trades.columns)
    open_col, close_col = db.find_open_close_time_cols(trades.columns)

    columns_used = [c for c in [pnl_col, open_col, close_col] if c]
    missing_columns = [name for name, col in {"pnl": pnl_col, "open_time": open_col, "close_time": close_col}.items() if col is None]

    durations = None
    if open_col and close_col:
        open_ts = db.to_datetime_series(trades[open_col], column_name=open_col)
        close_ts = db.to_datetime_series(trades[close_col], column_name=close_col)
        durations = (close_ts - open_ts).dt.total_seconds() / 60.0

    pnl = trades[pnl_col] if pnl_col else pd.Series(dtype="float64")
    metrics = _standard_metrics_frame(pnl, durations)
    metrics.to_csv(out_path, index=False)

    used = int(pd.to_numeric(pnl, errors="coerce").notna().sum()) if pnl_col else 0
    return {
        "trade_count_total": int(len(trades)),
        "trade_count_used": used,
        "columns_used": columns_used,
        "missing_columns": missing_columns,
        "generated_tables": ["tables/trade_summary.csv"],
        "table": table,
    }


def _write_regime_rank(conn: sqlite3.Connection, out: dict) -> dict:
    trades, _ = db.load_first_table(conn, ["recorder", "recorder_trades"])
    out_path = out["tables"] / "regime_rank.csv"
    required_cols = ["coin", "hour", "volatility_bucket", "expectancy", "profit_factor", "trade_count"]
    if trades is None:
        pd.DataFrame(columns=required_cols).to_csv(out_path, index=False)
        return {"generated_tables": ["tables/regime_rank.csv"], "missing_columns": ["trades_table"]}

    pnl_col = db.find_pnl_col(trades.columns)
    symbol_col = db.find_symbol_col(trades.columns)
    open_col, _ = db.find_open_close_time_cols(trades.columns)
    volatility_col = db.pick_first(trades.columns, ["volatility", "vol", "realized_vol", "atr", "atr_value", "atr_14"])

    missing = [name for name, col in {"pnl": pnl_col, "coin": symbol_col, "open_time": open_col, "volatility": volatility_col}.items() if col is None]
    if missing:
        pd.DataFrame(columns=required_cols).to_csv(out_path, index=False)
        return {"generated_tables": ["tables/regime_rank.csv"], "missing_columns": missing}

    work = trades[[pnl_col, symbol_col, open_col, volatility_col]].copy()
    work.columns = ["pnl", "coin", "open_time", "volatility"]
    work["pnl"] = pd.to_numeric(work["pnl"], errors="coerce")
    work["open_time"] = db.to_datetime_series(work["open_time"], column_name="open_time")
    work["volatility"] = pd.to_numeric(work["volatility"], errors="coerce")
    work = work.dropna(subset=["pnl", "open_time", "volatility", "coin"])

    if work.empty:
        pd.DataFrame(columns=required_cols).to_csv(out_path, index=False)
        return {"generated_tables": ["tables/regime_rank.csv"], "missing_columns": []}

    work["hour"] = work["open_time"].dt.hour
    work["volatility_bucket"] = pd.qcut(work["volatility"], q=min(5, work["volatility"].nunique()), duplicates="drop")
    grouped = work.groupby(["coin", "hour", "volatility_bucket"], dropna=False, observed=False)

    rows = []
    for keys, sub in grouped:
        pnl = sub["pnl"]
        gp = float(pnl[pnl > 0].sum())
        gl = float(abs(pnl[pnl < 0].sum()))
        pf = np.inf if gl == 0 and gp > 0 else (gp / gl if gl else np.nan)
        coin, hour, vol_bucket = keys
        rows.append(
            {
                "coin": coin,
                "hour": int(hour),
                "volatility_bucket": str(vol_bucket),
                "expectancy": float(pnl.mean()),
                "profit_factor": float(pf) if pd.notna(pf) else np.nan,
                "trade_count": int(len(pnl)),
            }
        )

    pd.DataFrame(rows, columns=required_cols).sort_values(["expectancy", "profit_factor"], ascending=False).to_csv(out_path, index=False)
    return {"generated_tables": ["tables/regime_rank.csv"], "missing_columns": []}


def _write_feature_importance(conn: sqlite3.Connection, out: dict) -> dict:
    trades, _ = db.load_first_table(conn, ["recorder", "recorder_trades"])
    out_path = out["tables"] / "feature_importance.csv"
    if trades is None:
        pd.DataFrame(columns=["feature", "importance"]).to_csv(out_path, index=False)
        return {"generated_tables": ["tables/feature_importance.csv"], "missing_columns": ["trades_table"]}

    pnl_col = db.find_pnl_col(trades.columns)
    if pnl_col is None:
        pd.DataFrame(columns=["feature", "importance"]).to_csv(out_path, index=False)
        return {"generated_tables": ["tables/feature_importance.csv"], "missing_columns": ["pnl"]}

    candidate_cols = [
        c
        for c in [
            db.find_symbol_col(trades.columns),
            db.pick_first(trades.columns, ["volatility", "vol", "realized_vol", "atr", "atr_14"]),
            db.find_leverage_col(trades.columns),
            db.find_step_col(trades.columns),
            db.find_side_col(trades.columns),
            db.find_dec_mode_col(trades.columns),
        ]
        if c is not None
    ]

    y = pd.to_numeric(trades[pnl_col], errors="coerce")
    rows = []
    for col in candidate_cols:
        s = trades[col]
        if pd.api.types.is_numeric_dtype(s):
            joined = pd.DataFrame({"x": pd.to_numeric(s, errors="coerce"), "y": y}).dropna()
            if len(joined) < 5:
                continue
            score = abs(joined["x"].corr(joined["y"]))
        else:
            joined = pd.DataFrame({"x": s.astype("string"), "y": y}).dropna()
            if len(joined) < 5:
                continue
            grp = joined.groupby("x", observed=False)["y"].agg(["mean", "count"])
            grand = float(joined["y"].mean())
            total = float(((joined["y"] - grand) ** 2).sum())
            between = float(((grp["mean"] - grand) ** 2 * grp["count"]).sum())
            score = between / total if total > 0 else np.nan
        if pd.notna(score):
            rows.append({"feature": col, "importance": float(score)})

    pd.DataFrame(rows, columns=["feature", "importance"]).sort_values("importance", ascending=False).to_csv(out_path, index=False)
    return {"generated_tables": ["tables/feature_importance.csv"], "missing_columns": []}


def _collect_generated_files(summary: dict, out: dict) -> tuple[list[str], list[str]]:
    generated_tables: set[str] = set()
    generated_graphs: set[str] = set()

    for module_result in summary.values():
        if not isinstance(module_result, dict):
            continue
        for t in module_result.get("tables", []):
            generated_tables.add(str(t))
        for c in module_result.get("charts", []):
            generated_graphs.add(str(c))

    for p in sorted(out["tables"].glob("*.csv")):
        generated_tables.add(str(p.relative_to(out["root"])))
    for p in sorted(out["graphs"].glob("*.png")):
        generated_graphs.add(str(p.relative_to(out["root"])))

    return sorted(generated_tables), sorted(generated_graphs)


def run_all(db_path: str | None = None, output_root: str | Path = "analysis_output") -> dict:
    out = db.ensure_output_dirs(output_root)
    conn = db.connect_db(db_path)
    summary: dict = {}
    try:
        for name, fn in MODULES:
            try:
                summary[name] = fn(conn, out)
            except Exception as exc:  # robust orchestration
                summary[name] = {"status": "error", "reason": str(exc)}

        trade_summary_meta = _write_trade_summary(conn, out)
        regime_rank_meta = _write_regime_rank(conn, out)
        feature_importance_meta = _write_feature_importance(conn, out)
    finally:
        conn.close()

    dashboard_path = dashboard.generate_dashboard(out["root"])
    summary["dashboard"] = {"status": "ok", "path": str(dashboard_path)}

    generated_tables, generated_graphs = _collect_generated_files(summary, out)
    summary.update(
        {
            "trade_count_total": trade_summary_meta["trade_count_total"],
            "trade_count_used": trade_summary_meta["trade_count_used"],
            "columns_used": trade_summary_meta["columns_used"],
            "missing_columns": sorted(
                set(
                    trade_summary_meta.get("missing_columns", [])
                    + regime_rank_meta.get("missing_columns", [])
                    + feature_importance_meta.get("missing_columns", [])
                )
            ),
            "generated_tables": generated_tables,
            "generated_graphs": generated_graphs,
        }
    )

    report_path = out["reports"] / "summary_report.json"
    report_path.write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full quant diagnostics for recorder.db")
    parser.add_argument("--db-path", default=None, help="Path to recorder.db")
    parser.add_argument("--output-root", default="analysis_output", help="Output directory root")
    args = parser.parse_args()
    summary = run_all(db_path=args.db_path, output_root=args.output_root)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
