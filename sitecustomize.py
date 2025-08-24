# sitecustomize.py
# Chargé automatiquement au démarrage de Python s'il est sur le PYTHONPATH.
# - charge /notebooks/.env
# - normalise les alias de secrets
# - charge la config pour initialiser les chemins DATA_ROOT
# - fait un préflight rapide (secrets + chemins) et écrit un green-flag

from __future__ import annotations
import json, os
from pathlib import Path

READY_PATH = Path("/notebooks/.scalp/READY.json")

def _load_dotenv_parent():
    try:
        from dotenv import load_dotenv
        load_dotenv("/notebooks/.env")
    except Exception:
        pass

def _apply_aliases():
    try:
        from engine.config.loader import apply_env_aliases
        apply_env_aliases()
    except Exception:
        pass

def _preflight():
    try:
        from engine.config.loader import load_config
        cfg = load_config()
        # vérifs minimales
        miss = []
        if not (cfg.get("secrets",{}).get("bitget",{}).get("access")):
            miss.append("BITGET_ACCESS_KEY")
        if not (cfg.get("secrets",{}).get("bitget",{}).get("secret")):
            miss.append("BITGET_SECRET_KEY")
        if miss:
            print("[-] Secrets manquants:", ", ".join(miss))
            return
        # chemins hors repo
        for key in ("data_dir","log_dir","reports_dir"):
            d = Path(cfg["runtime"][key])
            d.mkdir(parents=True, exist_ok=True)
        READY_PATH.parent.mkdir(parents=True, exist_ok=True)
        READY_PATH.write_text(json.dumps({"status":"ok","reason":"preflight"}, indent=2), encoding="utf-8")
        print("[✓] Préflight OK — green-flag écrit:", READY_PATH)
    except Exception as e:
        print("[!] Préflight non bloquant:", e)

try:
    if os.getenv("SKIP_PREFLIGHT","0").lower() not in ("1","true","yes","on"):
        _load_dotenv_parent()
        _apply_aliases()
        _preflight()
except Exception:
    pass