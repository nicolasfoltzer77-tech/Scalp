#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bootstrap global exécuté au démarrage (via import explicite dans bot.py).
- Corrige le PYTHONPATH (ajoute la racine du repo)
- S'assure que 'engine' & co sont de vrais paquets (création des __init__.py)
- Crée les dossiers data/reports par défaut
- Installe à la volée les dépendances manquantes (liste extensible)
- Pose un marqueur d'état et écrit un log de bootstrap

Idempotent: ré-exécutable sans effet de bord si tout est déjà OK.
"""

from __future__ import annotations
import os, sys, subprocess, json, time
from pathlib import Path

# ---------- Localisation du repo ----------
THIS_FILE   = Path(__file__).resolve()
TOOLS_DIR   = THIS_FILE.parent
REPO_ROOT   = TOOLS_DIR.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))  # permet "import engine", "import jobs", etc.

# ---------- Chemins par défaut (cohérents avec config.yaml) ----------
DEFAULT_DATA_DIR    = Path("/notebooks/scalp_data/data")
DEFAULT_REPORTS_DIR = Path("/notebooks/scalp_data/reports")
LOGS_DIR            = DEFAULT_REPORTS_DIR.parent / "logs"
BOOT_LOG            = LOGS_DIR / "bootstrap.log"
BOOT_MARKER         = LOGS_DIR / ".boot_ok.json"

# ---------- Paquets à créer si absents ----------
PKG_DIRS = [
    REPO_ROOT / "engine",
    REPO_ROOT / "engine" / "config",
    REPO_ROOT / "engine" / "strategies",
    REPO_ROOT / "engine" / "utils",
    REPO_ROOT / "jobs",
    REPO_ROOT / "tools",
]

def ensure_init_files():
    for d in PKG_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        initf = d / "__init__.py"
        if not initf.exists():
            initf.write_text("", encoding="utf-8")

# ---------- Dossiers runtime ----------
def ensure_runtime_dirs():
    for p in [
        DEFAULT_DATA_DIR,
        DEFAULT_DATA_DIR / "ohlcv",
        DEFAULT_REPORTS_DIR,
        LOGS_DIR,
    ]:
        p.mkdir(parents=True, exist_ok=True)

# ---------- Installation paquets ----------
def _pip_install(pkgs: list[str]):
    if not pkgs:
        return
    cmd = [sys.executable, "-m", "pip", "install", "--no-input"] + pkgs
    try:
        subprocess.check_call(cmd)
    except Exception as e:
        print(f"[BOOT] pip install failed for {pkgs}: {e}")

def ensure_packages():
    """
    Vérifie/installe les libs utilisées par SCALP.
    Ajoute ici au fur et à mesure (sûr pour re-run).
    """
    required = [
        # fondamentaux
        "numpy", "pandas", "pyyaml", "requests", "python-dateutil", "tqdm", "rich",
        # I/O & visu
        "pyarrow", "plotly", "altair",
        # backtest/ML potentiels
        "scipy", "scikit-learn", "statsmodels",
        # optimisation
        "optuna",
        # UI / tunnels (facultatif mais utile)
        "streamlit", "pydeck", "pyngrok",
        # TA classique (si on l’utilise plus tard)
        "ta",
    ]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.split("[",1)[0])
        except Exception:
            missing.append(pkg)

    if missing:
        _pip_install(missing)

# ---------- Journalisation ----------
def log_event(event: str, payload: dict | None = None):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"ts": int(time.time()), "event": event, **(payload or {})}
    with BOOT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def write_marker():
    info = {
        "ts": int(time.time()),
        "repo_root": str(REPO_ROOT),
        "python": sys.version,
        "paths": sys.path[:5],
        "data_dir": str(DEFAULT_DATA_DIR),
        "reports_dir": str(DEFAULT_REPORTS_DIR),
    }
    BOOT_MARKER.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- MAIN ----------
def main():
    try:
        ensure_init_files()
        ensure_runtime_dirs()
        ensure_packages()
        write_marker()
        log_event("bootstrap_ok", {"root": str(REPO_ROOT)})
    except Exception as e:
        log_event("bootstrap_error", {"err": repr(e)})
        # on n'élève pas l'exception pour ne pas bloquer l'appli

# Exécution immédiate si importé
main()