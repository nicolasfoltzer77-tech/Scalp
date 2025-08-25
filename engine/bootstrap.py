# engine/bootstrap.py
from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from engine.config.loader import load_config


log = logging.getLogger("bootstrap")


# ------------------------------------------------------------
# Dépendances minimales (légères) – on reste soft (pas de streamlit ici)
# ------------------------------------------------------------

_MIN_PKGS = [
    # pour la visu terminal (jobs/termboard ou health board)
    ("rich", "rich"),
    # utilitaires de base déjà utilisés dans le projet
    ("yaml", "pyyaml"),
    ("requests", "requests"),
]

def _is_installed(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except Exception:
        return False

def _pip_install(args: Iterable[str]) -> int:
    cmd = [sys.executable, "-m", "pip", "install", *list(args)]
    return subprocess.call(cmd)

def ensure_min_deps(extra: Optional[Iterable[str]] = None) -> None:
    """
    Installe en douceur les dépendances manquantes (rich, pyyaml, requests).
    Évite de planter le démarrage si pip échoue (on loggue seulement).
    """
    missing = []
    for mod, pip_name in _MIN_PKGS:
        if not _is_installed(mod):
            missing.append(pip_name)
    if extra:
        for name in extra:
            # si l'appelant veut forcer un paquet, on tente
            if not _is_installed(name):
                missing.append(name)

    if not missing:
        return

    try:
        log.info("[deps] installation manquante: %s", ", ".join(missing))
        _pip_install(missing)
    except Exception as e:
        log.warning("[deps] installation partielle: %s", e)


# ------------------------------------------------------------
# Chemins runtime (crée dossiers si absents)
# ------------------------------------------------------------

def ensure_paths() -> None:
    """
    Crée data_dir / reports_dir / logs_dir / tmp_dir si définis dans config.
    """
    cfg = load_config()
    rt = (cfg.get("runtime") or {})
    for key in ("data_dir", "reports_dir", "logs_dir", "tmp_dir"):
        p = Path(rt.get(key) or "").expanduser()
        if not p:
            continue
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log.warning("impossible de créer %s=%s: %s", key, p, e)


# ------------------------------------------------------------
# Exchange (Bitget REST) – tolérant aux signatures différentes
# ------------------------------------------------------------

def build_exchange():
    """
    Construit un client BitgetFuturesClient à partir de la conf.
    Supporte plusieurs signatures (paper/base optionnels) sans planter.
    """
    from engine.exchange.bitget_rest import BitgetFuturesClient  # existant dans ton repo

    cfg = load_config()
    ex_cfg = (cfg.get("exchange") or {}).get("bitget", {}) or {}
    trading = (cfg.get("trading") or {}) or {}

    ak = ex_cfg.get("access_key", "")
    sk = ex_cfg.get("secret_key", "")
    pp = ex_cfg.get("passphrase", "")
    base = ex_cfg.get("base", "https://api.bitget.com")
    paper = bool(trading.get("paper", True))

    # Essai 1: avec paper + base
    try:
        return BitgetFuturesClient(
            access_key=ak, secret_key=sk, passphrase=pp,
            paper=paper, base=base
        )
    except TypeError:
        pass
    # Essai 2: sans paper
    try:
        return BitgetFuturesClient(
            access_key=ak, secret_key=sk, passphrase=pp,
            base=base
        )
    except TypeError:
        pass
    # Essai 3: minimal
    try:
        return BitgetFuturesClient(
            access_key=ak, secret_key=sk, passphrase=pp
        )
    except TypeError as e:
        raise RuntimeError(f"BitgetFuturesClient incompatible avec la conf: {e}")


# ------------------------------------------------------------
# Entrée unique pour préparer l’environnement (appelée par app.run)
# ------------------------------------------------------------

def bootstrap_environment() -> None:
    """
    À appeler tôt au démarrage (depuis engine.app) :
      - installe les deps minimales (rich/pyyaml/requests) si besoin
      - prépare les dossiers runtime (data/reports/logs/tmp)
    """
    ensure_min_deps()
    ensure_paths()