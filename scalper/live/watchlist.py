# scalper/live/watchlist.py
from __future__ import annotations

"""
Watchlist minimaliste et robuste, pensée pour l'orchestrateur "fit".

Modes (via ENV):
  - WATCHLIST_MODE=static  : utilise TOP_SYMBOLS (ou défaut)
  - WATCHLIST_MODE=local   : calcule un TOPN depuis CSV (DATA_DIR) par (close*volume) ~24h
  - WATCHLIST_MODE=api     : placeholder "léger" -> TOP_SYMBOLS ou défaut

Autres ENV utiles:
  - TOP_SYMBOLS="BTCUSDT,ETHUSDT,..."   # prioritaire en static/api
  - TOPN=10                              # taille de la watchlist cible
  - DATA_DIR="/notebooks/data"           # où lire les CSV
  - QUIET=1                              # mute logs
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional

QUIET = int(os.getenv("QUIET", "0") or "0")

# ---------------------------------------------------------------------
# Défauts sûrs (liquidité élevée)
# ---------------------------------------------------------------------
DEFAULT_CANDIDATES = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT",
    "TRXUSDT", "MATICUSDT", "DOTUSDT", "TONUSDT", "NEARUSDT",
    "ATOMUSDT", "AAVEUSDT", "OPUSDT", "ARBUSDT", "SUIUSDT",
    "PEPEUSDT", "SHIBUSDT",
]

def _log(msg: str) -> None:
    if not QUIET:
        print(f"[watchlist] {msg}", flush=True)

def _parse_symbols_env(var: str) -> List[str]:
    raw = os.getenv(var, "")
    if not raw.strip():
        return []
    return [s.strip().upper() for s in raw.split(",") if s.strip()]

def _topn_value() -> int:
    try:
        return max(1, int(os.getenv("TOPN", "10")))
    except Exception:
        return 10

# ---------------------------------------------------------------------
# Mode STATIC/API (léger)
# ---------------------------------------------------------------------
def _from_env_or_default(topn: int) -> List[str]:
    env_syms = _parse_symbols_env("TOP_SYMBOLS")
    if env_syms:
        return env_syms[:topn]
    return DEFAULT_CANDIDATES[:topn]

# ---------------------------------------------------------------------
# Mode LOCAL : calcule TOPN via CSV (close*volume) ~24h
# Recherche d’abord 5m, sinon 1m, sinon fallback défaut
# ---------------------------------------------------------------------
def _data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "data")).resolve()

def _find_csvs() -> List[Tuple[Path, str]]:
    """
    Retourne [(path, timeframe_str)] pour les CSV présents en 5m/1m.
    Fichiers attendus: <SYMBOL>-<TF>.csv (ex: BTCUSDT-5m.csv)
    """
    root = _data_dir()
    if not root.exists():
        return []
    out: List[Tuple[Path, str]] = []
    for tf in ("5m", "1m"):
        out.extend([(p, tf) for p in root.glob(f"*-{tf}.csv") if p.is_file()])
    return out

def _symbol_from_csv_path(p: Path) -> Optional[str]:
    # BTCUSDT-5m.csv -> BTCUSDT
    name = p.name
    if "-" not in name:
        return None
    return name.split("-", 1)[0].upper()

def _score_csv(path: Path, tf: str) -> float:
    """
    Score = somme(close * volume) sur ~24h de barres.
    5m -> 288 barres ; 1m -> 1440 barres. Si moins, prend tout.
    """
    import pandas as pd
    try:
        df = pd.read_csv(path)
        cols = {c.lower(): c for c in df.columns}
        need = ["close", "volume"]
        for c in need:
            if c not in cols:
                return 0.0
        close = df[cols["close"]].astype(float)
        volume = df[cols["volume"]].astype(float)
        n = 288 if tf == "5m" else 1440
        if len(close) == 0:
            return 0.0
        c = close.tail(n)
        v = volume.tail(n)
        # simple robustesse longueur
        m = min(len(c), len(v))
        if m <= 0:
            return 0.0
        return float((c.tail(m) * v.tail(m)).sum())
    except Exception:
        return 0.0

def _local_top(topn: int) -> List[str]:
    csvs = _find_csvs()
    if not csvs:
        _log("mode local: aucun CSV trouvé → fallback défaut")
        return _from_env_or_default(topn)

    # Priorise 5m si dispo
    # regroupe par symbole et garde le meilleur score (5m prioritaire)
    scores: dict[str, float] = {}
    for path, tf in csvs:
        sym = _symbol_from_csv_path(path)
        if not sym:
            continue
        s = _score_csv(path, tf)
        if s <= 0:
            continue
        scores[sym] = max(scores.get(sym, 0.0), s)

    if not scores:
        _log("mode local: CSV illisibles → fallback défaut")
        return _from_env_or_default(topn)

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top = [sym for sym, _ in ordered[:topn]]
    _log(f"mode local → top={top}")
    return top

# ---------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------
def get_boot_watchlist() -> List[str]:
    """
    Watchlist initiale, en respectant WATCHLIST_MODE.
    - static : TOP_SYMBOLS ou DEFAULT_CANDIDATES (TOPN)
    - local  : calcule via CSV (DATA_DIR), fallback env/défaut
    - api    : identique à static (placeholder light)
    """
    mode = os.getenv("WATCHLIST_MODE", "static").strip().lower()
    topn = _topn_value()

    if mode == "local":
        syms = _local_top(topn)
    elif mode in ("static", "api"):
        syms = _from_env_or_default(topn)
    else:
        _log(f"mode inconnu '{mode}', fallback static")
        syms = _from_env_or_default(topn)

    _log(f"boot got: {syms}")
    return syms

# ---------------------------------------------------------------------
# Rafraîchissement (optionnel)
# ---------------------------------------------------------------------
def on_update() -> List[str]:
    """
    Permet de recalculer la watchlist à la demande (mêmes règles que boot).
    Idéal pour un cron ou une commande Telegram /watchlist_refresh (si tu l’ajoutes).
    """
    return get_boot_watchlist()