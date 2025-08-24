# sitecustomize.py
# Importé automatiquement par Python si présent sur le PYTHONPATH (répertoire courant).
# Rôle : charger les secrets depuis /notebooks/.env, normaliser les alias,
# charger la config YAML, puis lancer un pré‑flight et écrire un green‑flag.

from __future__ import annotations

import os

def _load_dotenv_parent():
    try:
        from dotenv import load_dotenv  # pip install python-dotenv si manquant
    except Exception:
        return
    # Règle historique du projet : .env au parent des notebooks (ex: /notebooks/.env)
    load_dotenv("/notebooks/.env")

def _apply_aliases_and_prefetch_cfg():
    try:
        from scalper.config.loader import apply_env_aliases, load_yaml_config
        apply_env_aliases()           # ne traite que les secrets (BITGET_*, TELEGRAM_*)
        # Chargement anticipé (au cas où certains modules le lisent tôt)
        _ = load_yaml_config()
    except Exception:
        pass

def _run_preflight():
    if os.getenv("SKIP_PREFLIGHT", "0").lower() in ("1", "true", "yes", "on"):
        return
    try:
        from scalper.selfcheck import preflight_or_die
        preflight_or_die(verbose=False)
    except SystemExit:
        raise
    except Exception:
        # On n'empêche pas l'exécution si le selfcheck plante pour une raison non critique
        pass

# Boot sequence
try:
    _load_dotenv_parent()            # charge /notebooks/.env
    _apply_aliases_and_prefetch_cfg()# normalise + précharge config.yaml
    _run_preflight()                 # valide et écrit le green-flag
except Exception:
    # Jamais bloquant
    pass