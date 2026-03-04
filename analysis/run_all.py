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


MODULES = [
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
