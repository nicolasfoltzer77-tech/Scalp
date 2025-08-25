# sitecustomize.py
from __future__ import annotations
import os
from pathlib import Path

# S'assurer que 'scalp' (racine du repo) est dans sys.path via import direct
# (en général déjà fait par bot.py, mais au cas où)
try:
    import sys
    ROOT = Path(__file__).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except Exception:
    pass

# Installer automatiquement les dépendances manquantes
try:
    from engine.utils.ensure_deps import ensure_minimal, ensure_from_requirements
    # d'abord requirements (idempotent), puis vérif minimale (streamlit, rich, etc.)
    ensure_from_requirements()
    ensure_minimal()
    print("[bootstrap] dépendances ok")
except Exception as e:
    print(f"[bootstrap] dépendances partielles: {e}")