#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bootstrap auto des dépendances pour SCALP.
Chargé automatiquement au démarrage Python.
"""

import os, sys, subprocess, importlib.util

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
REQ_FILE     = os.path.join(PROJECT_ROOT, "requirements.txt")

def log(msg): print(f"[bootstrap] {msg}", file=sys.stderr)

def ensure_from_requirements():
    if os.path.isfile(REQ_FILE):
        try:
            log(f"installing requirements.txt → {REQ_FILE}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQ_FILE])
        except subprocess.CalledProcessError as e:
            log(f"requirements install failed (code {e.returncode})")

def ensure_minimal():
    pkgs = ["pyyaml","rich","plotly","altair","pyarrow","pyngrok"]
    missing=[]
    for p in pkgs:
        if importlib.util.find_spec(p) is None:
            missing.append(p)
    if not missing:
        log("minimal deps ok")
        return
    log(f"installing missing minimal deps: {missing}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
    except subprocess.CalledProcessError as e:
        log(f"pip install {missing} failed (code {e.returncode})")

try:
    ensure_from_requirements()
    ensure_minimal()
    log("bootstrap done")
except Exception as e:
    log(f"bootstrap error: {e}")