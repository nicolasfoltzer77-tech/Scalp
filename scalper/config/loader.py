# scalper/config/loader.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Tuple, Any

# PyYAML est recommandé ; si absent on fonctionnera avec un dict vide.
try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

# ------------ Aliases ENV -> clés canoniques (SECRETS UNIQUEMENT) ------------
_ALIASES: Dict[str, Tuple[str, ...]] = {
    "BITGET_ACCESS_KEY": ("BITGET_API_KEY", "BITGET_KEY"),
    "BITGET_SECRET_KEY": ("BITGET_API_SECRET", "BITGET_SECRET"),
    "BITGET_PASSPHRASE": ("BITGET_API_PASSPHRASE", "BITGET_PASSWORD", "BITGET_API_PASSWORD"),
    "TELEGRAM_BOT_TOKEN": ("TELEGRAM_TOKEN", "TG_TOKEN"),
    "TELEGRAM_CHAT_ID": ("TG_CHAT_ID", "TELEGRAM_TO", "CHAT_ID"),
}

def _adopt_alias(target: str) -> None:
    if os.getenv(target):
        return
    for alt in _ALIASES.get(target, ()):
        v = os.getenv(alt)
        if v:
            os.environ[target] = v
            return

def apply_env_aliases() -> None:
    """Projette les aliases vers les clés canoniques (secrets)."""
    for k in _ALIASES:
        _adopt_alias(k)

# ------------ Chargement des paramètres généraux (YAML versionné) ------------
def load_yaml_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    """
    Charge le fichier YAML de paramètres généraux (PAS de secrets).
    Chemin par défaut : scalper/config/config.yaml (dans le repo).
    """
    if path is None:
        path = Path(__file__).resolve().parent / "config.yaml"
    path = Path(path)
    if yaml is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data

def load_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    """
    Fusionne :
      - paramètres généraux depuis YAML (versionné),
      - secrets depuis l'environnement (déjà chargés depuis /notebooks/.env).
    """
    cfg = load_yaml_config(path)
    apply_env_aliases()
    cfg.setdefault("secrets", {})
    cfg["secrets"]["bitget"] = {
        "access": os.getenv("BITGET_ACCESS_KEY") or "",
        "secret": os.getenv("BITGET_SECRET_KEY") or "",
        "passphrase": os.getenv("BITGET_PASSPHRASE") or "",
    }
    cfg["secrets"]["telegram"] = {
        "token": os.getenv("TELEGRAM_BOT_TOKEN") or "",
        "chat_id": os.getenv("TELEGRAM_CHAT_ID") or "",
    }
    return cfg

__all__ = ["apply_env_aliases", "load_yaml_config", "load_config"]