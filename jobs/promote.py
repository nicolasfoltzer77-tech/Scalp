#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, os, sys, time, logging, yaml
from copy import deepcopy

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
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(path)
    sh = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt); sh.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(sh)
    return logger

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--source", required=True, help="strategies.yml.next")
    ap.add_argument("--dest", default=DEFAULT_DEST, help="engine/config/strategies.yml")
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    rt = cfg.get("runtime", {})
    risk_mode = rt.get("risk_mode", "normal")
    age_mult = int(rt.get("age_mult", 5))
    data_dir = rt.get("data_dir", "/notebooks/scalp_data/data")
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")

    log = setup_logger(logs_dir)

    nxt = load_yaml(args.source)
    cand = nxt.get("strategies", {})
    dest_obj = load_yaml(args.dest, missing_ok=True)
    cur = dest_obj.get("strategies", {})

    if not cand:
        log.info("Aucune stratégie candidate.")
        dest_obj["strategies"] = cur
        save_yaml(dest_obj, args.dest)
        return

    now = int(time.time())
    changes = []

    # Expirer existantes si lifetime dépassé
    for key, strat in list(cur.items()):
        try: pair, tf = key.split(":")
        except ValueError: continue
        created = int(strat.get("created_at") or now)
        kmin = lifetime_minutes(tf, age_mult)
        exp = strat.get("expires_at") or (created + kmin*60)
        expired = now >= exp
        if expired and not strat.get("expired", False):
            strat["expired"] = True
            strat["expires_at"] = exp
            changes.append(f"EXPIRE {key}")

    pol = POLICY.get(risk_mode, POLICY["normal"])
    filt = {
        k: v for k, v in cand.items()
        if v.get("metrics", {}).get("pf", 0) >= pol["pf"]
        and v.get("metrics", {}).get("mdd", 1) <= pol["mdd"]
        and v.get("metrics", {}).get("trades", 0) >= pol["trades"]
    }

    if not filt:
        dest_obj["strategies"] = cur
        save_yaml(dest_obj, args.dest)
        log.info("Aucun candidat après filtrage risk_mode.")
        return

    for key, s in filt.items():
        try: _, tf = key.split(":")
        except ValueError:
            log.warning(f"Clé invalide {key}"); continue
        created = int(s.get("created_at") or now)
        kmin = lifetime_minutes(tf, age_mult)
        s["expires_at"] = created + kmin*60
        s["expired"] = False

        old = cur.get(key)
        if old is None:
            cur[key] = deepcopy(s); changes.append(f"ADD {key} PF={s['metrics']['pf']:.2f}")
        else:
            newer = int(s.get("created_at") or 0) > int(old.get("created_at") or 0)
            better = better_than(s.get("metrics", {}), old.get("metrics", {}))
            if (newer and better) or (old.get("expired", False) and better):
                cur[key] = deepcopy(s); changes.append(f"REPLACE {key}")

    dest_obj["strategies"] = cur
    save_yaml(dest_obj, args.dest)
    if changes:
        for c in changes: log.info(c)
    else:
        log.info("Promotion idempotente: aucun changement.")
    log.info(f"Écrit : {args.dest}")

if __name__ == "__main__":
    main()