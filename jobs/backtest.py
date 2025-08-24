from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from engine.config.loader import load_config
from engine.backtest.loader_csv import load_csv_ohlcv
from engine.backtest.engine import run_backtest_once, compute_metrics, grid_params

def main() -> int:
    ap = argparse.ArgumentParser(description="Backtests grid -> DATA_ROOT/reports")
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--tfs", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = load_config()
    data_dir = Path(cfg["runtime"]["data_dir"])
    reports_dir = Path(args.out or cfg["runtime"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]

    summary: List[Dict[str, Any]] = []
    best: Dict[str, Dict[str, Any]] = {}

    for sym in symbols:
        for tf in tfs:
            csv_path = data_dir / f"{sym.replace('/','').replace('_','')}-{tf}.csv"
            if not csv_path.exists():
                print(f"[!] CSV manquant: {csv_path} (backfill d'abord)")
                continue
            df = load_csv_ohlcv(csv_path)
            best_score = None
            best_params = None
            for p in grid_params():
                res = run_backtest_once(sym, tf, df, params=p)
                m = res["metrics"]
                summary.append({"symbol": sym, "tf": tf, **p, **m})
                sc = float(m["score"])
                if (best_score is None) or (sc > best_score):
                    best_score, best_params = sc, p
            if best_params:
                best[f"{sym}:{tf}"] = best_params

    (reports_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (reports_dir / "strategies.yml.next").write_text(json.dumps({"strategies": best}, indent=2), encoding="utf-8")
    print(f"[✓] Résumé -> {reports_dir/'summary.json'}")
    print(f"[✓] Brouillon stratégie -> {reports_dir/'strategies.yml.next'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())