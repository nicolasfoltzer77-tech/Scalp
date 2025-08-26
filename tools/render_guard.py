#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, sys, hashlib, subprocess

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_YAML  = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")

def _load_yaml(path):
    import yaml
    if not os.path.isfile(path):
        return {}
    return yaml.safe_load(open(path,"r",encoding="utf-8")) or {}

def _hash(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        import hashlib
        return hashlib.md5(f.read()).hexdigest()

def main():
    cfg = _load_yaml(CONFIG_YAML)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    summary = os.path.join(reports_dir, "summary.json")
    guard = os.path.join(reports_dir, ".last_summary_hash")

    cur = _hash(summary)
    prev = ""
    if os.path.isfile(guard):
        prev = open(guard, "r", encoding="utf-8").read().strip()

    if cur and cur == prev:
        print("[render-guard] summary inchangé → skip render_report.py")
        return

    env = os.environ.copy()
    env["SCALP_REPORTS_DIR"] = reports_dir
    script = os.path.join(PROJECT_ROOT, "tools", "render_report.py")
    print("[render-guard] summary modifié → génération HTML…")
    subprocess.check_call([sys.executable, script], env=env, cwd=PROJECT_ROOT)

    if cur:
        with open(guard, "w", encoding="utf-8") as f:
            f.write(cur)

if __name__ == "__main__":
    main()