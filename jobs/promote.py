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
    logger = logging.getLogger("promote"); logger.setLevel(logging.INFO); logger.handlers.clear()
    fh = logging.FileHandler(path); sh = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"); fh.setFormatter(fmt); sh.setFormatter(fmt)
    logger.addHandler(fh); logger.addHandler(sh); return logger

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--source", default=None, help="strategies.yml.next (déduit si absent)")
    ap.add_argument("--dest", default=DEFAULT_DEST)
    args = ap.parse_args()

    cfg = load_yaml(args.config)
    rt = cfg.get("runtime", {})
    risk_mode = rt.get("risk_mode", "normal")
    age_mult = int(rt.get("age_mult", 5))
    data_dir = rt.get("data_dir", "/notebooks/scalp_data/data")
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    log = setup_logger(logs_dir)

    # source par défaut si None
    source = args.source or os.path.join(reports_dir, "strategies.yml.next")

    nxt = load_yaml(source, missing_ok=True)
    cand = nxt.get("strategies", {})
    dest_obj = load_yaml(args.dest, missing_ok=True)
    cur = dest_obj.get("strategies", {})

    if not cand:
        log.info(f"Aucune stratégie candidate