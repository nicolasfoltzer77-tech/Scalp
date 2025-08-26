#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, sys, json, time, yaml
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from engine.utils.io_safe import atomic_write_json, atomic_write_text, backup_last_good
from engine.utils.logging_setup import setup_logger
from engine.strategies.base import Metrics, StrategyBase
from engine.strategies import registry as strat_registry
from tools.exp_tracker import new_run_id, log_event

CONFIG_YAML   = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")
STRATS_NEXT   = lambda rd: os.path.join(rd, "strategies.yml.next")
SUMMARY_JSON  = lambda rd: os.path.join(rd, "summary.json")
WATCHLIST_YML = lambda rd: os.path.join(rd, "watchlist.yml")
EXPS_DIR      = lambda rd: os.path.join(rd, "experiments")

def load_yaml(path, missing_ok=False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def save_yaml(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_text(yaml.safe_dump(obj, sort_keys=True, allow_unicode=True, default_flow_style=False), path)

def ohlcv_path(data_dir: str, pair: str, tf: str) -> str:
    return os.path.join(data_dir, "ohlcv", pair, f"{tf}.csv")

def load_csv_fast(path: str):
    import pandas as pd
    usecols = ["timestamp","open","high","low","close","volume"]
    if not os.path.isfile(path): return None
    try:
        df = pd.read_csv(path, usecols=usecols, dtype={
            "timestamp":"int64","open":"float64","high":"float64","low":"float64","close":"float64","volume":"float64"
        }, engine="c")
        df = df.sort_values("timestamp").dropna()
        return df
    except Exception:
        return None

def make_row(pair: str, tf: str, met: Metrics) -> Dict:
    return {
        "pair": pair, "tf": tf,
        "pf": round(met.pf,6), "mdd": round(met.mdd,6),
        "trades": int(met.trades), "wr": round(met.wr,6),
        "sharpe": round(met.sharpe,6),
    }

def make_candidate(pair: str, tf: str, strat: StrategyBase, met: Metrics, now_ts: int) -> Tuple[str, Dict]:
    params = strat.describe()
    key = f"{pair}:{tf}"
    cand = {
        **{k:v for k,v in params.items() if k!="name"},
        "name": params.get("name"),
        "created_at": now_ts,
        "expires_at": None,
        "expired": False,
        "metrics": {
            "pf": round(met.pf,6),
            "mdd": round(met.mdd,6),
            "trades": int(met.trades),
            "wr": round(met.wr,6),
            "sharpe": round(met.sharpe,6),
        }
    }
    return key, cand

def load_watchlist(reports_dir: str, topN: int | None = None) -> List[str]:
    wl = load_yaml(WATCHLIST_YML(reports_dir), missing_ok=True)
    pairs = wl.get("pairs") or wl.get("watchlist") or []
    pairs = [p for p in pairs if isinstance(p, str)]
    return pairs[:topN] if topN else pairs

def process_pair_tf(data_dir: str, pair: str, tf: str, strat_name: str, strat_params: Optional[dict]) -> Tuple[Dict, Tuple[str, Dict]]:
    strat = strat_registry.create(strat_name, strat_params)
    df = load_csv_fast(ohlcv_path(data_dir, pair, tf))
    met = strat.backtest(df)
    now_ts = int(time.time())
    row = make_row(pair, tf, met)
    key, cand = make_candidate(pair, tf, strat, met, now_ts)
    return row, (key, cand)

def run():
    cfg = load_yaml(CONFIG_YAML, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    data_dir = rt.get("data_dir", "/notebooks/scalp_data/data")
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    tf_list = rt.get("tf_list", ["1m","5m","15m"])
    topN = int(rt.get("topN", 10))

    # stratégie (runtime.strategy_name / runtime.strategy_params)
    strat_name = (rt.get("strategy_name") or "ema_atr_v1").strip()
    strat_params = rt.get("strategy_params") or {}

    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log = setup_logger("backtest", os.path.join(logs_dir, "backtest.log"))

    run_id = new_run_id()
    log_event(EXPS_DIR(reports_dir), run_id, {"event":"start", "strategy": strat_name, "params": strat_params, "tf_list": tf_list, "topN": topN})

    pairs = load_watchlist(reports_dir, topN=topN)
    if not pairs:
        log.info({"event":"no_watchlist"}); 
        log_event(EXPS_DIR(reports_dir), run_id, {"event":"no_watchlist"})
        return

    rows: List[Dict] = []
    cands: Dict[str, Dict] = {}

    from multiprocessing import cpu_count
    max_workers = min(8, (cpu_count() or 2))
    tasks = []
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        for pair in pairs:
            for tf in tf_list:
                tasks.append(ex.submit(process_pair_tf, data_dir, pair, tf, strat_name, strat_params))
        for fut in as_completed(tasks):
            try:
                row, (key, cand) = fut.result()
                rows.append(row); cands[key] = cand
            except Exception as e:
                log.info({"event":"pair_tf_error","err":str(e)})
                log_event(EXPS_DIR(reports_dir), run_id, {"event":"pair_tf_error", "err": str(e)})

    summary_path = SUMMARY_JSON(reports_dir)
    next_path = STRATS_NEXT(reports_dir)

    backup_last_good(summary_path)
    atomic_write_json({"generated_at": int(time.time()), "risk_mode": rt.get("risk_mode","normal"), "rows": rows}, summary_path)

    backup_last_good(next_path)
    save_yaml({"strategies": cands}, next_path)

    log.info({"event":"done","rows":len(rows),"cands":len(cands)})
    log_event(EXPS_DIR(reports_dir), run_id, {"event":"done", "rows": len(rows), "cands": len(cands)})

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(json.dumps({"lvl":"ERROR","msg":str(e)}))
        sys.exit(1)