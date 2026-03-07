from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json

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


def run_all(db_path: str | None = None, output_root: str | Path = "analysis_output") -> dict:
    out = db.ensure_output_dirs(output_root)
    conn = db.connect_db(db_path)
    summary = {}
    try:
        for name, fn in MODULES:
            try:
                summary[name] = fn(conn, out)
            except Exception as exc:  # robust orchestration
                summary[name] = {"status": "error", "reason": str(exc)}
    finally:
        conn.close()

    dashboard_path = dashboard.generate_dashboard(out["root"])
    summary["dashboard"] = {"status": "ok", "path": str(dashboard_path)}

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
