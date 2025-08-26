#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, sys, pathlib, time, json, yaml, subprocess, traceback
from typing import Dict, List, Tuple

# -- ensure repo root on sys.path (for 'engine' imports)
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[1])  # /notebooks/scalp
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import sitecustomize  # bootstrap global

from engine.config.loader import load_config  # ton loader existant si présent, sinon lecture yaml locale

CFG_PATH = os.path.join(_REPO_ROOT, "engine", "config", "config.yaml")
REPORTS_DIR = None
DATA_DIR = None

def _read_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _now_ms():
    return int(time.time() * 1000)

def list_pairs_from_watchlist(reports_dir: str) -> List[str]:
    wpath = os.path.join(reports_dir, "watchlist.yml")
    if not os.path.isfile(wpath): return []
    doc = _read_yaml(wpath)
    pairs = doc.get("pairs") or doc.get("watchlist") or []
    return [p for p in pairs if isinstance(p, str)]

def ohlcv_path(pair: str, tf: str) -> str:
    return os.path.join(DATA_DIR, "ohlcv", pair, f"{tf}.csv")

def file_age_minutes(path: str) -> float:
    try:
        mtime = os.path.getmtime(path)
        return (time.time() - mtime) / 60.0
    except FileNotFoundError:
        return float("inf")

def tf_minutes(tf: str) -> int:
    # ex: "1m", "5m", "15m"
    assert tf.endswith("m")
    return int(tf[:-1])

def compute_status(pairs: List[str], tf_list: List[str], age_mult: int) -> Dict:
    """
    Renvoie:
      {
        "generated_at": ts,
        "counts": {"MIS":X,"OLD":Y,"DAT":Z,"OK":K},
        "matrix": [{"pair":"BTCUSDT","1m":"DAT","5m":"OK","15m":"OLD"}, ...],
        "notes": "MIS=no data · OLD=stale · DAT=data no strat · OK=ready"
      }
    """
    counts = {"MIS":0,"OLD":0,"DAT":0,"OK":0}
    matrix = []

    # lire strategies.yml pour savoir quelles paires/TF sont "promues"
    strats_path = os.path.join(_REPO_ROOT, "engine", "config", "strategies.yml")
    promoted = {}
    if os.path.isfile(strats_path):
        doc = _read_yaml(strats_path) or {}
        for k, v in (doc.get("strategies") or {}).items():
            promoted[k] = v

    for pair in pairs:
        row = {"pair": pair}
        for tf in tf_list:
            path = ohlcv_path(pair, tf)
            if not os.path.isfile(path):
                st = "MIS"
            else:
                age_m = file_age_minutes(path)
                lifetime_m = age_mult * tf_minutes(tf)
                key = f"{pair}:{tf}"
                has_strat = key in promoted and not promoted[key].get("expired", False)
                if age_m > lifetime_m:
                    st = "OLD"
                elif has_strat:
                    st = "OK"
                else:
                    st = "DAT"
            counts[st] += 1
            row[tf] = st
        matrix.append(row)

    return {
        "generated_at": int(time.time()),
        "counts": counts,
        "matrix": matrix,
        "notes": "MIS=no data · OLD=stale · DAT=data present, no active strategy · OK=fresh data + active strategy"
    }

def write_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def run_module(modname: str, *args, detach: bool=False) -> Tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _REPO_ROOT + (":" + env.get("PYTHONPATH","") if env.get("PYTHONPATH") else "")
    cmd = [sys.executable, "-m", modname, *args]
    try:
        if detach:
            subprocess.Popen(cmd, cwd=_REPO_ROOT, env=env)
            return 0, ""
        else:
            cp = subprocess.run(cmd, cwd=_REPO_ROOT, env=env, capture_output=True, text=True)
            return cp.returncode, (cp.stderr or "")
    except Exception as e:
        return 1, repr(e)

def main():
    global REPORTS_DIR, DATA_DIR
    cfg = _read_yaml(CFG_PATH)  # si pas de loader spécifique
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    DATA_DIR = rt.get("data_dir", "/notebooks/scalp_data/data")
    REPORTS_DIR = rt.get("reports_dir", "/notebooks/scalp_data/reports")

    tf_list = list(rt.get("tf_list", ["1m","5m","15m"]))
    age_mult = int(rt.get("age_mult", 5))
    pairs = list_pairs_from_watchlist(REPORTS_DIR)

    # 1) refresh déjà assuré ailleurs dans ton bot (sinon appeller jobs.refresh ici)

    # 2) backtest
    rc_bt, err_bt = run_module("jobs.backtest")
    # 3) promote (SANS --draft)
    src_next = os.path.join(REPORTS_DIR, "strategies.yml.next")
    rc_pr, err_pr = run_module("jobs.promote", "--source", src_next)

    # 4) calcul statut & persist
    stat = compute_status(pairs, tf_list, age_mult)
    write_json(stat, os.path.join(REPORTS_DIR, "status.json"))

    # 5) trace erreurs récentes pour le dashboard
    last = {
        "ts": int(time.time()),
        "backtest_rc": rc_bt, "backtest_err": err_bt.strip(),
        "promote_rc": rc_pr, "promote_err": err_pr.strip(),
    }
    write_json(last, os.path.join(REPORTS_DIR, "last_errors.json"))

    # 6) affichage terminal compact (comme ton termboard)
    def col(s): 
        return {"MIS":"\x1b[90mMIS\x1b[0m","OLD":"\x1b[31mOLD\x1b[0m","DAT":"\x1b[33mDAT\x1b[0m","OK":"\x1b[32mOK\x1b[0m"}[s]
    print("[maintainer] État (PAIR×TF)")
    print("PAIR | " + " | ".join(f"{tf:>3}" for tf in tf_list))
    print("-----|" + "|".join("---" for _ in tf_list))
    for row in stat["matrix"]:
        print(f"{row['pair']:<4} | " + " | ".join(col(row[tf]) for tf in tf_list))
    print(f"[maintainer] INFO: backtest RC={rc_bt} · promote RC={rc_pr}")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("[maintainer] FATAL:\n" + traceback.format_exc())
        sys.exit(1)