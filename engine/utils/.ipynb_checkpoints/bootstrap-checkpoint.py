# engine/utils/bootstrap.py
from __future__ import annotations
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple

_MARK_DIR = Path("/notebooks/.scalp")
_MARK_DIR.mkdir(parents=True, exist_ok=True)
STATE = _MARK_DIR / "DEPS.json"

# import_name -> pip_spec
CORE_REQS: Dict[str, str] = {
    "requests": "requests>=2.31",
    "pandas": "pandas>=2.1",
    "numpy": "numpy>=1.26",
    "yaml": "PyYAML>=6.0",
    "dotenv": "python-dotenv>=1.0",
}
DASH_REQS: Dict[str, str] = {"streamlit": "streamlit>=1.33"}
CCXT_REQS: Dict[str, str] = {"ccxt": "ccxt>=4.0.0"}


def _need(import_name: str) -> bool:
    try:
        importlib.import_module(import_name)
        return False
    except Exception:
        return True


def _pip(spec: str) -> Tuple[bool, str]:
    try:
        # upgrade pip une seule fois par session (léger)
        if not getattr(_pip, "_upgraded", False):
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _pip._upgraded = True  # type: ignore[attr-defined]
        proc = subprocess.run([sys.executable, "-m", "pip", "install", spec],
                              capture_output=True, text=True, check=False)
        ok = (proc.returncode == 0)
        return ok, (proc.stdout + proc.stderr)[-3000:]
    except Exception as e:
        return False, f"pip failed: {e}"


def ensure_dependencies(*, with_dash: bool = True, with_ccxt: bool = True) -> Dict[str, str]:
    """
    Idempotent: installe seulement ce qui manque.
    Écrit l'état dans /notebooks/.scalp/DEPS.json
    """
    plan: Dict[str, str] = {}
    reqs = dict(CORE_REQS)
    if with_dash:
        reqs.update(DASH_REQS)
    if with_ccxt:
        reqs.update(CCXT_REQS)

    for import_name, spec in reqs.items():
        if _need(import_name):
            ok, log_tail = _pip(spec)
            plan[spec] = "installed" if ok else f"failed: {log_tail}"
        else:
            plan[spec] = "ok"

    try:
        STATE.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    except Exception:
        pass
    return plan