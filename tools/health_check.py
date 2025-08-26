#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Health check rapide (dépendances + chemins + fichiers clés).
Usage: python tools/health_check.py
"""

from __future__ import annotations
import os, sys, importlib, json, shutil, time, yaml

OK = "OK"
KO = "KO"

REQUIRED_PKGS = [
    ("pandas",   "pd"),
    ("numpy",    "np"),
    ("pyyaml",   "yaml"),
    ("rich",     "rich"),
    ("plotly",   "plotly"),
    ("altair",   "altair"),
    ("pyarrow",  "pyarrow"),
]

CONFIG_PATH = "engine/config/config.yaml"

def check_imports():
    out = []
    for pkg, _alias in REQUIRED_PKGS:
        try:
            m = importlib.import_module(pkg)
            ver = getattr(m, "__version__", "?")
            out.append((pkg, OK, ver))
        except Exception as e:
            out.append((pkg, KO, str(e).split("\n", 1)[0]))
    return out

def load_yaml(path, missing_ok=False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def fmt(pct):
    try:
        return f"{pct:.1f}%"
    except Exception:
        return "n/a"

def main():
    print("== SCALP • health_check ==")
    # 1) Imports
    print("\n[1/4] Dépendances Python")
    for pkg, status, info in check_imports():
        print(f" - {pkg:<10} : {status}  ({info})")

    # 2) Config + dossiers
    print("\n[2/4] Configuration & dossiers")
    cfg = load_yaml(CONFIG_PATH, missing_ok=True)
    if not cfg:
        print(f" - {CONFIG_PATH} : {KO} (introuvable)")
        data_dir = "/notebooks/scalp_data/data"
        reports_dir = "/notebooks/scalp_data/reports"
    else:
        print(f" - {CONFIG_PATH} : {OK}")
        rt = cfg.get("runtime", {})
        data_dir = rt.get("data_dir", "/notebooks/scalp_data/data")
        reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
        print(f"   data_dir    = {data_dir}")
        print(f"   reports_dir = {reports_dir}")
        print(f"   risk_mode   = {rt.get('risk_mode', 'n/a')}")
        print(f"   termboard_enabled = {rt.get('termboard_enabled', False)}")

    for path in (data_dir, reports_dir):
        print(f" - dir {path} : {OK if os.path.isdir(path) else KO}")

    # 3) Fichiers clés
    print("\n[3/4] Fichiers clés")
    summ = os.path.join(reports_dir, "summary.json")
    nxt  = os.path.join(reports_dir, "strategies.yml.next")
    cur  = "engine/config/strategies.yml"
    for p in (summ, nxt, cur):
        if os.path.isfile(p):
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(os.path.getmtime(p)))
            print(f" - {p} : {OK} (modifié {ts} UTC)")
        else:
            print(f" - {p} : {KO}")

    # 4) Disque (espace libre)
    print("\n[4/4] Espace disque")
    try:
        total, used, free = shutil.disk_usage("/")
        used_pct = used / total * 100.0
        print(f" - free={free//(1024**3)} GiB • used={fmt(used_pct)}")
    except Exception:
        print(" - n/a")

    print("\nConseil: si plotly/altair manquent → vérifier `sitecustomize.py` et/ou relancer `bot.py` pour bootstrap.")

if __name__ == "__main__":
    main()