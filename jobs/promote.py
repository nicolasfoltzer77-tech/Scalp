#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, os, sys, time, json, yaml, subprocess
from copy import deepcopy
from typing import Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# utils
sys.path.append(PROJECT_ROOT)
from engine.utils.io_safe import atomic_write_text, backup_last_good
from engine.utils.logging_setup import setup_logger

DEFAULT_CONFIG = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")
DEFAULT_DEST   = os.path.join(PROJECT_ROOT, "engine", "config", "strategies.yml")

POLICY = {
    "conservative": {"pf": 1.4, "mdd": 0.15, "trades": 35},
    "normal":       {"pf": 1.3, "mdd": 0.20, "trades": 30},
    "aggressive":   {"pf": 1.2, "mdd": 0.30, "trades": 25},
}

def load_yaml(path, missing_ok=False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def dump_yaml(obj) -> str:
    return yaml.safe_dump(obj, sort_keys=True, allow_unicode=True, default_flow_style=False)

def tf_minutes(tf: str) -> int:
    if tf.endswith("m"): return int(tf[:-1])
    if tf.endswith("h"): return int(tf[:-1]) * 60
    if tf.endswith("d"): return int(tf[:-1]) * 1440
    raise ValueError(f"TF non supporté: {tf}")

def lifetime_minutes(tf: str, k: int) -> int:
    return k * tf_minutes(tf)

def _score_row(r: Dict) -> float:
    pf=float(r.get("pf",0)); mdd=float(r.get("mdd",1))
    sh=float(r.get("sharpe",0)); wr=float(r.get("wr",0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _pass(r, pol):
    return (r.get("pf",0)>=pol["pf"]) and (r.get("mdd",1)<=pol["mdd"]) and (r.get("trades",0)>=pol["trades"])

def print_top(reports_dir: str, risk_mode: str, k:int=12, logger=None):
    path = os.path.join(reports_dir, "summary.json")
    try:
        sm = json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        if logger: logger.info("summary.json introuvable")
        else: print("[TOP] summary.json introuvable")
        return
    rows = sm.get("rows", [])
    if not rows:
        if logger: logger.info("Aucun résultat en base.")
        else: print("[TOP] Aucun résultat en base.")
        return
    pol = POLICY.get(risk_mode, POLICY["normal"])
    rows.sort(key=_score_row, reverse=True)
    passed = sum(1 for r in rows if _pass(r,pol))
    if logger:
        logger.info(json.dumps({"event":"top_summary","risk":risk_mode,"total":len(rows),"pass":passed}, ensure_ascii=False))
    else:
        print(f"[TOP] PASS={passed}/{len(rows)} (policy={risk_mode})")

def _call_render_guard(project_root: str):
    env = os.environ.copy()
    script = os.path.join(project_root, "tools", "render_guard.py")
    if not os.path.isfile(script):
        print("[render] tools/render_guard.py introuvable (skip).")
        return
    try:
        subprocess.check_call([sys.executable, script], env=env, cwd=project_root)
    except subprocess.CalledProcessError as e:
        print(f"[render] render_guard a échoué (code {e.returncode}).")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--source", default=None)
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--top-k", type=int, default=12)
    args = ap.parse_args()

    cfg = load_yaml(args.config, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    risk_mode = rt.get("risk_mode", "normal")
    age_mult  = int(rt.get("age_mult", 5))
    data_dir  = rt.get("data_dir", "/notebooks/scalp_data/data")
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    logger = setup_logger("promote", os.path.join(logs_dir, "promote.log"))

    source = args.source or os.path.join(reports_dir, "strategies.yml.next")
    nxt = load_yaml(source, missing_ok=True); cand = nxt.get("strategies", {})
    dest_obj = load_yaml(args.dest, missing_ok=True); cur = dest_obj.get("strategies", {})

    if not cand:
        logger.info(json.dumps({"event":"promote","status":"no_candidates","source":source}, ensure_ascii=False))
        print_top(reports_dir, risk_mode, k=args.top_k, logger=logger)
        _call_render_guard(PROJECT_ROOT)
        return

    # expiry des actives
    now = int(time.time())
    changes = []
    for key, strat in list(cur.items()):
        try: _, tf = key.split(":")
        except ValueError: continue
        created = int(strat.get("created_at") or now)
        exp = strat.get("expires_at") or (created + (lifetime_minutes(tf, age_mult)*60))
        if now >= exp and not strat.get("expired", False):
            strat["expired"] = True; strat["expires_at"] = exp; changes.append({"EXPIRE": key})

    pol = POLICY.get(risk_mode, POLICY["normal"])
    filt = {
        k: v for k, v in cand.items()
        if v.get("metrics", {}).get("pf", 0) >= pol["pf"]
        and v.get("metrics", {}).get("mdd", 1) <= pol["mdd"]
        and v.get("metrics", {}).get("trades", 0) >= pol["trades"]
    }

    if not filt:
        dest_obj["strategies"] = cur
        # backup last-good puis écriture atomique
        backup_last_good(args.dest)
        atomic_write_text(dump_yaml(dest_obj), args.dest)
        logger.info(json.dumps({"event":"promote","status":"no_pass_after_policy"}, ensure_ascii=False))
        print_top(reports_dir, risk_mode, k=args.top_k, logger=logger)
        _call_render_guard(PROJECT_ROOT)
        return

    # merge “meilleure ou plus récente”
    for key, s in filt.items():
        try: _, tf = key.split(":")
        except ValueError:
            logger.info(json.dumps({"event":"bad_key","key":key}, ensure_ascii=False))
            continue
        created = int(s.get("created_at") or now)
        s["expires_at"] = created + (lifetime_minutes(tf, age_mult)*60)
        s["expired"] = False

        old = cur.get(key)
        if old is None:
            cur[key] = deepcopy(s); changes.append({"ADD": key, "pf": s.get("metrics",{}).get("pf")})
        else:
            newer = int(s.get("created_at") or 0) > int(old.get("created_at") or 0)
            better = (
                s.get("metrics", {}).get("pf", 0) > old.get("metrics", {}).get("pf", 0)
                or (
                    s.get("metrics", {}).get("pf", 0) == old.get("metrics", {}).get("pf", 0)
                    and s.get("metrics", {}).get("mdd", 1) < old.get("metrics", {}).get("mdd", 1)
                )
                or s.get("metrics", {}).get("sharpe", 0) > old.get("metrics", {}).get("sharpe", 0)
            )
            if (newer and better) or (old.get("expired", False) and better):
                cur[key] = deepcopy(s); changes.append({"REPLACE": key})

    dest_obj["strategies"] = cur
    # backup + écriture atomique
    backup_last_good(args.dest)
    atomic_write_text(dump_yaml(dest_obj), args.dest)

    logger.info(json.dumps({"event":"promote","status":"done","changes":changes}, ensure_ascii=False))
    print_top(reports_dir, risk_mode, k=args.top_k, logger=logger)

    # rendu debouncé
    _call_render_guard(PROJECT_ROOT)

if __name__ == "__main__":
    main()