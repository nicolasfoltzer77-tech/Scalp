# engine/utils/ensure_deps.py
from __future__ import annotations
import importlib, subprocess, sys
from pathlib import Path
from typing import Iterable

DEFAULT_PKGS = [
    # ce set couvre l'app + termboard + dash
    "pandas", "numpy", "pyyaml", "requests", "tqdm",
    "aiohttp", "websockets",
    "rich", "streamlit", "plotly", "matplotlib",
    "python-telegram-bot",
]

def _installed(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False

def _pip_install(args: list[str]) -> int:
    return subprocess.call([sys.executable, "-m", "pip", "install", *args])

def ensure_minimal(extra: Iterable[str] = ()) -> None:
    """Installe ce qui manque (module par module) sans planter le boot."""
    missing = []
    # mapping module->pip-name si différent
    name_map = {
        "python-telegram-bot": "python-telegram-bot",
        "pyyaml": "pyyaml",
        "matplotlib": "matplotlib",
        "streamlit": "streamlit",
        "plotly": "plotly",
        "rich": "rich",
        "tqdm": "tqdm",
        "aiohttp": "aiohttp",
        "websockets": "websockets",
        "pandas": "pandas",
        "numpy": "numpy",
        "requests": "requests",
    }
    modules = list(DEFAULT_PKGS) + list(extra or [])
    for pkg in modules:
        mod = pkg
        # pour certains noms pip = module
        if pkg == "python-telegram-bot":
            mod = "telegram"
        if pkg == "pyyaml":
            mod = "yaml"
        if not _installed(mod):
            missing.append(name_map.get(pkg, pkg))
    if missing:
        try:
            print(f"[deps] installation manquante: {', '.join(missing)}")
            _pip_install(missing)
        except Exception as e:
            print(f"[deps] avertissement: installation partielle: {e}")

def ensure_from_requirements() -> None:
    """Si requirements.txt existe, tente un install (idempotent)."""
    req = Path(__file__).resolve().parents[2] / "requirements.txt"
    if req.exists():
        try:
            print("[deps] pip install -r requirements.txt (auto)")
            _pip_install(["-r", str(req)])
        except Exception as e:
            print(f"[deps] échec install -r requirements.txt: {e}")