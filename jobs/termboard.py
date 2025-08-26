#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Termboard minimal :
- Respecte runtime.termboard_enabled (false par défaut) → ne rien afficher et sortir 0.
- Si true, affiche un résumé ultra-concis (1 ligne) basé sur summary.json s'il existe.
"""

from __future__ import annotations
import os, sys, json, time, yaml

DEFAULT_CONFIG = "engine/config/config.yaml"
REPORTS_FALLBACK = "/notebooks/scalp_data/reports/summary.json"

def load_yaml(path: str, missing_ok: bool = False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def read_summary(path: str):
    if not os.path.isfile(path): return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def main():
    # config
    cfg_path = DEFAULT_CONFIG
    if len(sys.argv) >= 2 and sys.argv[1].endswith(".yaml"):
        cfg_path = sys.argv[1]
    cfg = load_yaml(cfg_path, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    enabled = bool(rt.get("termboard_enabled", False))  # défaut = False (silencieux)

    if not enabled:
        # mode silencieux → rien n'afficher, pas d’erreur
        return

    # sinon: mini résumé (1 ligne)
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    summary_path = os.path.join(reports_dir, "summary.json")
    if not os.path.isfile(summary_path):
        summary_path = REPORTS_FALLBACK

    sm = read_summary(summary_path) or {}
    rows = sm.get("rows", [])
    risk_mode = sm.get("risk_mode", "n/a")
    n = len(rows)
    if n == 0:
        print(f"[termboard] summary.json absent ou vide • risk={risk_mode}")
        return

    # Compter “PASS” vs policy si présente dans summary
    pol = sm.get("policy") or {}
    def pass_policy(r):
        pf = r.get("pf", 0); mdd = r.get("mdd", 1); tr = r.get("trades", 0)
        return (
            pf >= pol.get("pf", 1.3)
            and mdd <= pol.get("mdd", 0.2)
            and tr >= pol.get("trades", 30)
        )
    passed = sum(1 for r in rows if pass_policy(r))
    print(f"[termboard] backtests={n} • pass={passed} • risk={risk_mode}")

if __name__ == "__main__":
    main()