#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import argparse, os, sys, time, logging, yaml, json, subprocess
from copy import deepcopy
from typing import Dict, List

DEFAULT_CONFIG = "engine/config/config.yaml"
DEFAULT_DEST = "engine/config/strategies.yml"

POLICY = {
    "conservative": {"pf": 1.4, "mdd": 0.15, "trades": 35},
    "normal":       {"pf": 1.3, "mdd": 0.20, "trades": 30},
    "aggressive":   {"pf": 1.2, "mdd": 0.30, "trades": 25},
}

def load_yaml(path, missing_ok=False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def save_yaml(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, sort_keys=True, allow_unicode=True, default_flow_style=False)

def tf_minutes(tf: str) -> int:
    if tf.endswith("m"): return int(tf[:-1])
    if tf.endswith("h"): return int(tf[:-1]) * 60
    if tf.endswith("d"): return int(tf[:-1]) * 1440
    raise ValueError(f"TF non supporté: {tf}")

def lifetime_minutes(tf: str, k: int) -> int:
    return k * tf_minutes(tf)

def better_than(a: dict, b: dict) -> bool:
    if a.get("pf", 0) != b.get("pf", 0): return a.get("pf", 0) > b.get("pf", 0)
    if a.get("mdd", 1) != b.get("mdd", 1): return a.get("mdd", 1) < b.get("mdd", 1)
    return a.get("sharpe", 0) > b.get("sharpe", 0)

def setup_logger(logs_dir: str) -> logging.Logger:
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, "promote.log")
    logger = logging.getLogger("promote")
    logger.setLevel(logging.INFO); logger.handlers.clear()
    fh = logging.FileHandler(path); sh = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt); sh.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(sh); return logger

# ---- TOP console
RISK_POLICIES = POLICY
def _score_row(r: Dict) -> float:
    pf=float(r.get("pf",0)); mdd=float(r.get("mdd",1))
    sh=float(r.get("sharpe",0)); wr=float(r.get("wr",0))
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def _pass(r, pol):
    return (r.get("pf",0)>=pol["pf"]) and (r.get("mdd",1)<=pol["mdd"]) and (r.get("trades",0)>=pol["trades"])

def _explain_fail(r, pol):
    why=[]
    if r.get("pf",0)<pol["pf"]: why.append(f"PF {r.get('pf',0):.2f}<{pol['pf']:.2f}")
    if r.get("mdd",1)>pol["mdd"]: why.append(f"MDD {r.get('mdd',1):.2%}>{pol['mdd']:.0%}")
    if r.get("trades",0)<pol["trades"]: why.append(f"TR {r.get('trades',0)}<{pol['trades']}")
    return "OK" if not why else "; ".join(why)

def print_top(reports_dir: str, risk_mode: str, k:int=12):
    path = os.path.join(reports_dir, "summary.json")
    try:
        sm = json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        print("[TOP] summary.json introuvable"); return
    rows = sm.get("rows", [])
    if not rows: print("[TOP] Aucun résultat en base."); return
    pol = RISK_POLICIES.get(risk_mode, RISK_POLICIES["normal"])
    rows.sort(key=_score_row, reverse=True)
    hdr = f"TOP {k} — meilleurs backtests (policy={risk_mode})"
    print("\n" + "="*len(hdr)); print(hdr); print("="*len(hdr))
    print("RANK | PAIR:TF | PF | MDD | TR | WR | Sharpe | Note | Status")
    for i,r in enumerate(rows[:k],1):
        status = "PASS" if _pass(r,pol) else f"FAIL ({_explain_fail(r,pol)})"
        note = _score_row(r)
        print(f"{i:>4} | {r['pair']}:{r['tf']:>3} | {r.get('pf',0):>4.2f} | "
              f"{r.get('mdd',0):>4.0%} | {r.get('trades',0):>3} | {r.get('wr',0):>4.0%} | "
              f"{r.get('sharpe',0):>5.2f} | {note:>4.2f} | {status}")
    passed = sum(1 for r in rows if _pass(r,pol))
    print(f"[TOP] Résumé: {passed} PASS / {len(rows)} total")

def render_html_dashboard(project_root: str, reports_dir: str):
    render_py = os.path.join(project_root, "tools", "render_report.py")
    if not os.path.isfile(render_py):
        print("[render] tools/render_report.py introuvable, skip.")
        return
    env = os.environ.copy()
    env["SCALP_REPORTS_DIR"] = reports_dir
    try:
        subprocess.check_call([sys.executable, render_py], env=env)
    except subprocess.CalledProcessError as e:
        print(f"[render] échec génération HTML (code {e.returncode}).")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--source", default=None)
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--backup", action="store_true", help="(ignoré, compat bot.py)")
    ap.add_argument("--top-k", type=int, default=12)
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    rt = cfg.get("runtime", {})
    risk_mode = rt.get("risk_mode", "normal")
    age_mult = int(rt.get("age_mult", 5))
    data_dir = rt.get("data_dir", "/notebooks/scalp_data/data")
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log = setup_logger(logs_dir)

    source = args.source or os.path.join(reports_dir, "strategies.yml.next")
    nxt = load_yaml(source, missing_ok=True); cand = nxt.get("strategies", {})
    dest_obj = load_yaml(args.dest, missing_ok=True); cur = dest_obj.get("strategies", {})

    if not cand:
        log.info(f"Aucune stratégie candidate ({source}).")
        print_top(reports_dir, risk_mode, k=args.top_k)
        render_html_dashboard(project_root, reports_dir)
        return

    now = int(time.time()); changes = []

    # expiry
    for key, strat in list(cur.items()):
        try: _, tf = key.split(":")
        except ValueError: continue
        created = int(strat.get("created_at") or now)
        exp = strat.get("expires_at") or (created + lifetime_minutes(tf, age_mult)*60)
        if now >= exp and not strat.get("expired", False):
            strat["expired"] = True; strat["expires_at"] = exp; changes.append(f"EXPIRE {key}")

    pol = POLICY.get(risk_mode, POLICY["normal"])
    filt = {
        k: v for k, v in cand.items()
        if v.get("metrics", {}).get("pf", 0) >= pol["pf"]
        and v.get("metrics", {}).get("mdd", 1) <= pol["mdd"]
        and v.get("metrics", {}).get("trades", 0) >= pol["trades"]
    }
    if not filt:
        dest_obj["strategies"] = cur; save_yaml(dest_obj, args.dest)
        log.info("Aucun candidat après filtrage risk_mode.")
        print_top(reports_dir, risk_mode, k=args.top_k)
        render_html_dashboard(project_root, reports_dir)
        return

    for key, s in filt.items():
        try: _, tf = key.split(":")
        except ValueError: log.warning(f"Clé invalide {key}"); continue
        created = int(s.get("created_at") or now)
        s["expires_at"] = created + lifetime_minutes(tf, age_mult)*60
        s["expired"] = False

        old = cur.get(key)
        if old is None:
            cur[key] = deepcopy(s); changes.append(f"ADD {key} PF={s['metrics']['pf']:.2f}")
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
                cur[key] = deepcopy(s); changes.append(f"REPLACE {key}")

    dest_obj["strategies"] = cur; save_yaml(dest_obj, args.dest)
    for c in changes or ["Promotion idempotente: aucun changement."]:
        log.info(c)
    log.info(f"Écrit : {args.dest}")

    print_top(reports_dir, risk_mode, k=args.top_k)
    render_html_dashboard(project_root, reports_dir)

if __name__ == "__main__":
    main()