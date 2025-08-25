# cli.py  (à la racine du repo)
from __future__ import annotations
import argparse

def parse_cli() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="SCALP — launcher")
    ap.add_argument("--once", action="store_true", help="Exécuter une seule passe orchestrateur")
    ap.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARN/ERROR (défaut: INFO)")
    return ap.parse_args()