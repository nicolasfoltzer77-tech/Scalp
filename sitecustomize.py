"""
sitecustomize.py
Exécuté automatiquement par Python au démarrage,
utile pour corriger sys.path, créer les __init__.py,
et s’assurer que toutes les dépendances critiques sont dispo.
"""

import os, sys, pathlib, subprocess

# --- 1) Corrige le PYTHONPATH ---
REPO_ROOT = str(pathlib.Path(__file__).resolve().parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --- 2) Garantit que les dossiers sont des paquets ---
for pkg in [
    "engine",
    "engine/config",
    "engine/strategies",
    "engine/utils",
    "jobs",
    "tools"
]:
    pkg_path = pathlib.Path(REPO_ROOT) / pkg
    pkg_path.mkdir(parents=True, exist_ok=True)
    initf = pkg_path / "__init__.py"
    if not initf.exists():
        initf.write_text("", encoding="utf-8")

# --- 3) Vérifie les dépendances essentielles ---
REQUIRED_PKGS = [
    "pyyaml",
    "numpy",
    "pandas",
    "plotly",
    "altair",
    "rich",
    "tqdm",
    "scipy",
    "optuna"
]

def ensure(pkgs):
    missing = []
    for p in pkgs:
        try:
            __import__(p)
        except ImportError:
            missing.append(p)
    if missing:
        print(f"[BOOT] Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)

ensure(REQUIRED_PKGS)

print(f"[BOOT] sitecustomize chargé depuis {REPO_ROOT}")
