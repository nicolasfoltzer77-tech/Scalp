import os, sys, pathlib, subprocess, time, json

# --- Corrige PYTHONPATH ---
REPO_ROOT = str(pathlib.Path(__file__).resolve().parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# --- Garantit que engine/ et jobs/ sont des paquets ---
for pkg in ["engine", "engine/config", "engine/strategies", "engine/utils", "jobs", "tools"]:
    pkg_path = pathlib.Path(REPO_ROOT) / pkg
    pkg_path.mkdir(parents=True, exist_ok=True)
    initf = pkg_path / "__init__.py"
    if not initf.exists():
        initf.write_text("", encoding="utf-8")

# --- Vérifie que PyYAML et autres libs minimales sont installées ---
def ensure(pkgs):
    missing = []
    for p in pkgs:
        try:
            __import__(p)
        except ImportError:
            missing.append(p)
    if missing:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)

ensure(["pyyaml", "numpy", "pandas", "plotly", "altair"])