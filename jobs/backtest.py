#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Backtest plug-in (version légère sans multiprocessing)
- Charge config.yaml + backtest_config.json + entries_config.json
- Détermine paires/TF
- Exécute la stratégie plugin
- Applique contraintes min_trades / min_pf aux candidats
- Écrit summary.json + strategies.yml.next + trace JSONL
"""

from __future__ import annotations
import os, sys, json, time, yaml
from typing import List, Dict, Tuple, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from engine.utils.io_safe import atomic_write_json, atomic_write_text, backup_last_good
from engine.utils.logging_setup import setup_logger
from engine.strategies.base import Metrics, StrategyBase
from engine.strategies import registry as strat_registry
from tools.exp_tracker import new_run_id, log_event

CONFIG_YAML    = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")
BACKTEST_JSON  = os.path.join(PROJECT_ROOT, "backtest_config.json")
ENTRIES_JSON   = os.path.join(PROJECT_ROOT, "entries_config.json")
STRATS_NEXT    = lambda rd: os.path.join(rd, "strategies.yml.next")
SUMMARY_JSON   = lambda rd: os.path.join(rd, "summary.json")
WATCHLIST_YML  = lambda rd: os.path.join(rd, "watchlist.yml")
EXPS_DIR       = lambda rd: os.path.join(rd, "experiments")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEBUG_TXT = os.path.join(PROJECT_ROOT, "debug.txt")
DEBUG_HTML = os.path.join(PROJECT_ROOT, "debug.html")

def _score(row):
    # même logique simple que le dashboard
    pf=float(row.get("pf",0)); mdd=float(row.get("mdd",1)); sh=float(row.get("sharpe",0)); wr=float(row.get("wr",0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def write_debug_artifacts(rows, top_k=20, meta=None):
    rows_sorted = sorted(rows, key=_score, reverse=True)
    # TXT
    lines = []
    lines.append("RANK | PAIR | TF | PF | MDD | TR | WR | Sharpe | Note")
    for i, r in enumerate(rows_sorted[:top_k], 1):
        note = _score(r)
        lines.append(f"{i:>4} | {r['pair']:<8} | {r['tf']:<4} | {r['pf']:.3f} | {r['mdd']:.1%} | "
                     f"{r['trades']:>3} | {r['wr']:.1%} | {r['sharpe']:.2f} | {note:.2f}")
    if meta:
        lines.append("")
        lines.append(f"meta: {json.dumps(meta, ensure_ascii=False)}")
    with open(DEBUG_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # HTML mini (optionnel)
    html = ["<!doctype html><meta charset='utf-8'><title>SCALP Debug</title><pre>"]
    html.extend(lines)
    html.append("</pre>")
    with open(DEBUG_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

def load_yaml(path, missing_ok=False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def save_yaml(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_text(yaml.safe_dump(obj, sort_keys=True, allow_unicode=True, default_flow_style=False), path)

def load_json(path, missing_ok=True):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

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

def run():
    # 1) runtime
    cfg = load_yaml(CONFIG_YAML, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}

    data_dir    = rt.get("data_dir", "./data")
    reports_dir = rt.get("reports_dir", "./reports")
    tf_list     = list(rt.get("tf_list", ["1m","5m","15m"]))
    topN        = int(rt.get("topN", 10))

    # 2) JSON configs
    bt_cfg = load_json(BACKTEST_JSON, missing_ok=True) or {}
    en_cfg = load_json(ENTRIES_JSON,  missing_ok=True) or {}

    assets_json = list(bt_cfg.get("assets", []) or [])
    tfs_json    = list(bt_cfg.get("timeframes", []) or [])
    if tfs_json: tf_list = tfs_json

    strat_name   = (rt.get("strategy_name") or "ema_atr_v1").strip()
    strat_params = dict(rt.get("strategy_params") or {})

    # 3) loggers
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log = setup_logger("backtest", os.path.join(logs_dir, "backtest.log"))
    run_id = new_run_id()

    # 4) paires
    if assets_json:
        pairs = assets_json[:topN] if topN else assets_json
        src = "backtest_config.assets"
    else:
        pairs = load_watchlist(reports_dir, topN=topN)
        src = "watchlist.yml"
    if not pairs:
        log.info({"event":"no_pairs","src":src})
        log_event(EXPS_DIR(reports_dir), run_id, {"event":"no_pairs","src":src})
        return

    # 5) contraintes
    constraints = (bt_cfg.get("constraints") or {})
    min_trades = int(constraints.get("min_trades", 0))
    min_pf     = float(constraints.get("min_pf", 0.0))

    costs       = (bt_cfg.get("costs") or {})
    walkf       = (bt_cfg.get("walk_forward") or {})
    opti        = (bt_cfg.get("optimization") or {})

    log_event(EXPS_DIR(reports_dir), run_id, {
        "event":"start",
        "strategy": strat_name,
        "params": strat_params,
        "pairs_src": src,
        "pairs": pairs,
        "tf_list": tf_list,
        "constraints": constraints,
        "costs": costs,
        "walk_forward": walkf,
        "optimization": opti,
        "entries_cfg_present": bool(en_cfg),
    })

    # 6) boucle séquentielle
    rows: List[Dict] = []
    cands_all: Dict[str, Dict] = {}

    for pair in pairs:
        for tf in tf_list:
            try:
                strat = strat_registry.create(strat_name, strat_params)
                df = load_csv_fast(ohlcv_path(data_dir, pair, tf))
                met = strat.backtest(df)
                now_ts = int(time.time())
                rows.append(make_row(pair, tf, met))
                key, cand = make_candidate(pair, tf, strat, met, now_ts)
                cands_all[key] = cand
            except Exception as e:
                log.info({"event":"pair_tf_error","pair":pair,"tf":tf,"err":str(e)})
                log_event(EXPS_DIR(reports_dir), run_id, {"event":"pair_tf_error","pair":pair,"tf":tf,"err":str(e)})

    # 7) appliquer contraintes
    cands = {}
    for k, v in cands_all.items():
        met = v.get("metrics", {})
        if int(met.get("trades", 0)) < min_trades: continue
        if float(met.get("pf", 0.0)) < min_pf: continue
        cands[k] = v

    # 8) sorties
    summary_path = SUMMARY_JSON(reports_dir)
    next_path    = STRATS_NEXT(reports_dir)

    summary_obj = {
        "generated_at": int(time.time()),
        "risk_mode": rt.get("risk_mode","normal"),
        "meta": {
            "pairs_src": src, "pairs": pairs, "tf_list": tf_list,
            "constraints": constraints, "costs": costs,
            "walk_forward": walkf, "optimization": opti,
            "entries_cfg_present": bool(en_cfg),
            "strategy": {"name": strat_name, "params": strat_params},
        },
        "rows": rows
    }

    backup_last_good(summary_path)
    atomic_write_json(summary_obj, summary_path)

    backup_last_good(next_path)
    save_yaml({"strategies": cands}, next_path)

    log.info({"event":"done","rows":len(rows),"cands_total":len(cands_all),"cands_after_constraints":len(cands)})
    log_event(EXPS_DIR(reports_dir), run_id, {
        "event":"done","rows":len(rows),
        "cands_total":len(cands_all),
        "cands_after_constraints":len(cands)
    })

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(json.dumps({"lvl":"ERROR","msg":str(e)}))
        sys.exit(1)