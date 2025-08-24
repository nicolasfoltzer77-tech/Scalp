# sitecustomize.py
# Chargé automatiquement par Python s'il est sur le PYTHONPATH (racine du repo).
# - charge /notebooks/.env
# - AUTO-INSTALL des dépendances manquantes (core + dash + ccxt)
# - prépare DATA_ROOT (data/logs/reports)
# - écrit un green-flag JSON avec l'état des checks

from __future__ import annotations
import json
import os
from pathlib import Path

READY_PATH = Path("/notebooks/.scalp/READY.json")

def _load_dotenv_parent() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv("/notebooks/.env")
    except Exception:
        pass

def _auto_install() -> dict:
    """
    Installation auto, toujours activée (idempotente).
    Tu peux limiter via variables d'env si besoin:
      DISABLE_DASH=1  -> n'installe pas streamlit
      DISABLE_CCXT=1  -> n'installe pas ccxt
    """
    try:
        from engine.utils.bootstrap import ensure_dependencies  # type: ignore
    except Exception:
        # bootstrap de secours minimal (si chemins pas encore dispo)
        return {"bootstrap": "missing"}
    with_dash = os.getenv("DISABLE_DASH", "").lower() not in {"1", "true", "yes"}
    with_ccxt = os.getenv("DISABLE_CCXT", "").lower() not in {"1", "true", "yes"}
    try:
        return ensure_dependencies(with_dash=with_dash, with_ccxt=with_ccxt)
    except Exception as e:
        return {"ensure_dependencies": f"failed: {e}"}

def _paths_from_env() -> dict:
    data_root = os.getenv("DATA_ROOT", "/notebooks/scalp_data")
    d = Path(data_root)
    for sub in ("data", "logs", "reports"):
        try:
            (d / sub).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return {"DATA_ROOT": str(d), "data_dir": str(d / "data"),
            "log_dir": str(d / "logs"), "reports_dir": str(d / "reports")}

def _write_ready(payload: dict) -> None:
    try:
        READY_PATH.parent.mkdir(parents=True, exist_ok=True)
        READY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("[✓] Préflight OK — green-flag:", READY_PATH)
    except Exception:
        pass

def _apply_env_aliases() -> None:
    try:
        from engine.config.loader import apply_env_aliases  # type: ignore
        apply_env_aliases()
    except Exception:
        pass

try:
    _load_dotenv_parent()
    _apply_env_aliases()
    deps = _auto_install()
    paths = _paths_from_env()

    # mini check secrets (non bloquant)
    miss = []
    if not (os.getenv("BITGET_ACCESS_KEY") and os.getenv("BITGET_SECRET_KEY") and os.getenv("BITGET_PASSPHRASE")):
        miss.append("BITGET_*")
    if not (os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")):
        miss.append("TELEGRAM_*")

    _write_ready({"status": "ok", "deps": deps, "paths": paths, "missing": miss})
except Exception as e:
    _write_ready({"status": "partial", "error": str(e)})