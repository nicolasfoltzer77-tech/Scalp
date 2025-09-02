# engine/watchlist.py
from __future__ import annotations
import os, json
from pathlib import Path
from typing import List, Dict, Any

DEFAULT_BOOT = ["BTCUSDT", "ETHUSDT"]
DEFAULT_TFS  = ["1m"]

def _parse_env_list(var: str, default: List[str]) -> List[str]:
    txt = os.getenv(var, "").strip()
    if not txt:
        return default
    # autorise séparateurs virgule / espaces
    items = [x.strip().upper() for x in txt.replace(";", ",").replace(" ", ",").split(",") if x.strip()]
    return items or default

def _dedup_usdt(symbols: List[str]) -> List[str]:
    """Garde uniquement les paires *USDT (filtre aussi les bases doublons si besoin)."""
    out, seen = [], set()
    for s in symbols:
        s = s.upper()
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        if base in seen:
            continue
        seen.add(base)
        out.append(s)
    return out

def _load_watchlist_file(limit: int | None = None) -> List[str]:
    """Lit /opt/scalp/reports/watchlist.json|yml et renvoie une liste de symboles."""
    root = Path("/opt/scalp/reports")
    # 1) JSON prioritaire
    pj = root / "watchlist.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text())
            if isinstance(data, dict):
                if "symbols" in data and isinstance(data["symbols"], list):
                    syms = [str(x).upper() for x in data["symbols"]]
                elif "items" in data and isinstance(data["items"], list):
                    syms = [str(it.get("sym") or it.get("symbol") or it.get("pair") or "").upper()
                            for it in data["items"]]
                else:
                    syms = []
            elif isinstance(data, list):
                syms = [str(x).upper() for x in data]
            else:
                syms = []
            syms = [s for s in syms if s]  # drop vides
            syms = _dedup_usdt(syms)
            return syms[:limit] if limit else syms
        except Exception as e:
            print(f"[watchlist] erreur lecture JSON: {e}")

    # 2) YAML optionnel
    py = root / "watchlist.yml"
    if py.exists():
        try:
            import yaml  # nécessite python3-yaml (apt install -y python3-yaml)
            data = yaml.safe_load(py.read_text())
            syms: List[str]
            if isinstance(data, dict):
                if "symbols" in data:
                    syms = [str(x).upper() for x in data["symbols"]]
                elif "items" in data:
                    syms = [str(it.get("sym") or it.get("symbol") or it.get("pair") or "").upper()
                            for it in data["items"]]
                else:
                    syms = []
            elif isinstance(data, list):
                syms = [str(x).upper() for x in data]
            else:
                syms = []
            syms = [s for s in syms if s]
            syms = _dedup_usdt(syms)
            return syms[:limit] if limit else syms
        except Exception as e:
            print(f"[watchlist] erreur lecture YAML: {e}")

    return []

def load(limit: int | None = None) -> Dict[str, Any]:
    """
    Charge la watchlist pour le moteur/scanner.
    Ordre:
      1) /opt/scalp/reports/watchlist.json | watchlist.yml
      2) variables d'env MANUAL_SYMBOLS / TFS
      3) fallback DEFAULT_BOOT / DEFAULT_TFS
    """
    # 1) fichiers reports
    file_syms = _load_watchlist_file(limit=limit)
    if file_syms:
        tfs = _parse_env_list("TFS", DEFAULT_TFS)
        return {"symbols": file_syms, "tfs": tfs}

    # 2) variables d'env
    env_syms = _parse_env_list("MANUAL_SYMBOLS", DEFAULT_BOOT)
    tfs = _parse_env_list("TFS", DEFAULT_TFS)
    env_syms = _dedup_usdt(env_syms)
    return {"symbols": env_syms[:limit] if limit else env_syms, "tfs": tfs}
