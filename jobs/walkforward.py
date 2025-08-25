#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, os, sys, json, time, logging
import yaml
import numpy as np
import pandas as pd

DEFAULT_CONFIG = "engine/config/config.yaml"

def load_yaml(p):
    with open(p, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def setup_logger(dir_):
    os.makedirs(dir_, exist_ok=True)
    log = logging.getLogger("walkforward"); log.setLevel(logging.INFO)
    log.handlers.clear()
    fh = logging.FileHandler(os.path.join(dir_, "walkforward.log"))
    sh = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt); sh.setFormatter(fmt)
    log.addHandler(fh); log.addHandler(sh)
    return log

def load_csv(data_dir: str, pair: str, tf: str, limit: int | None):
    p = os.path.join(data_dir, "ohlcv", pair, f"{tf}.csv")
    df = pd.read_csv(p)
    ts0 = df["timestamp"].iloc[0]
    if isinstance(ts0, (int, np.integer)) and ts0 < 2e10:
        df["timestamp"] = df["timestamp"].astype(np.int64) * 1000
    return df.sort_values("timestamp").tail(limit or len(df)).reset_index(drop=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--pair", required=True)
    ap.add_argument("--entry-tf", default="1m")
    ap.add_argument("--schema-backtest", required=True)
    ap.add_argument("--schema-entries", required=True)
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--optuna", action="store_true")
    ap.add_argument("--trials", type=int, default=30)
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    rt = cfg.get("runtime", {})
    data_dir = rt.get("data_dir"); reports_dir = rt.get("reports_dir")
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    log = setup_logger(logs_dir)

    from engine.strategies.twolayer_scalp import (
        load_combined_or_split, compute_regime_score_multi_tf,
        build_entries_frame, run_backtest_exec
    )
    from engine.utils.walkforward import make_segments
    sb, se = load_combined_or_split(None, args.schema_backtest, args.schema_entries)
    dir_tfs = sb["timeframes"]["direction"]

    df_entry = load_csv(data_dir, args.pair, args.entry_tf, args.limit)
    idx = pd.to_datetime(df_entry["timestamp"], unit="ms", utc=True)
    df_entry.index = idx

    df_by_tf = {}
    for rtf in dir_tfs:
        df_r = load_csv(data_dir, args.pair, rtf, args.limit*5)
        df_r.index = pd.to_datetime(df_r["timestamp"], unit="ms", utc=True)
        df_by_tf[rtf] = df_r

    wf = sb.get("backtest", {}).get("walk_forward", {"train_days": 90, "test_days": 30, "segments": 6})
    segs = make_segments(df_entry.index, wf["train_days"], wf["test_days"], wf["segments"])
    log.info(f"{len(segs)} segments WF")

    def eval_once(s_back, s_entries) -> dict:
        p_buy = compute_regime_score_multi_tf(df_by_tf, s_back)
        p_buy = p_buy.reindex(df_entry.index, method="ffill")
        df_exec = pd.concat([df_entry.copy(), build_entries_frame(df_entry.copy(), s_entries)], axis=1)
        return run_backtest_exec(df_exec, p_buy, s_back, s_entries)

    # Baseline sans tuning (évalue sur chaque segment test)
    res = []
    for sg in segs:
        test = df_entry.loc[sg.test_start:sg.test_end]
        if test.empty: continue
        r = eval_once(sb, se)
        res.append(r)
    agg = {
        "pf_mean": float(np.mean([r["pf"] for r in res] or [0])),
        "mdd_max": float(np.max([r["mdd"] for r in res] or [0])),
        "wr_mean": float(np.mean([r["wr"] for r in res] or [0])),
        "sharpe_mean": float(np.mean([r["sharpe"] for r in res] or [0])),
        "segments": len(res),
    }

    # Optuna (optionnel)
    best = {}
    if args.optuna:
        try:
            import optuna
            def objective(trial):
                sback = json.loads(json.dumps(sb))
                sback["regime_layer"]["indicators"]["ema"]["fast"]["5m"] = trial.suggest_int("ema_fast_5m", 7, 14)
                sback["regime_layer"]["indicators"]["ema"]["slow"]["5m"] = trial.suggest_int("ema_slow_5m", 21, 34)
                sback["regime_layer"]["softmax_temperature"] = trial.suggest_float("tau", 0.25, 0.5)
                r = eval_once(sback, se)
                return r["pf"] - 0.5*r["mdd"]
            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=args.trials)
            best = study.best_params
        except Exception as e:
            log.warning(f"Optuna indisponible/erreur: {e}")

    out = {"pair": args.pair, "entry_tf": args.entry_tf, "wf": agg, "optuna_best": best}
    os.makedirs(reports_dir, exist_ok=True)
    with open(os.path.join(reports_dir, f"walkforward_{args.pair}_{args.entry_tf}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log.info("WF résumé écrit.")

if __name__ == "__main__":
    main()