# /opt/scalp/webviz/realtimeviz/adapter.py
from __future__ import annotations
from typing import Any, Dict, List, Callable, Optional
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# Détection souple des fonctions du projet (plusieurs chemins possibles)
# -----------------------------------------------------------------------------
def _try_import(paths: List[str]) -> Optional[Callable]:
    for p in paths:
        mod_name, func_name = p.rsplit(":", 1)
        try:
            mod = __import__(mod_name, fromlist=[func_name])
            fn = getattr(mod, func_name, None)
            if callable(fn):
                print(f"[adapter] Found: {p}")
                return fn
        except Exception as e:
            pass
    return None

# fonctions candidates (adapte si besoin)
FN_WATCHLIST = _try_import([
    "scalp.watchlist:get_current_watchlist",
    "watchlist:get_current_watchlist",
    "core.watchlist:get_current_watchlist",
    "src.watchlist:get_current_watchlist",
])

FN_SIGNALS = _try_import([
    "scalp.signals:detect_signals",
    "signals:detect_signals",
    "core.signals:detect_signals",
    "src.signals:detect_signals",
])

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# -----------------------------------------------------------------------------
# Normalisation HEATMAP
# -----------------------------------------------------------------------------
def _normalize_score(raw: Any) -> float:
    """
    Convertit divers formats de "score" en [0..1].
    - si déjà 0..1 -> clamp
    - si -10..10   -> (x+10)/20
    - si -1..1     -> (x+1)/2
    - sinon 0.0
    """
    try:
        x = float(raw)
    except Exception:
        return 0.0
    if 0.0 <= x <= 1.0:
        return max(0.0, min(1.0, x))
    if -10.0 <= x <= 10.0:
        return (x + 10.0) / 20.0
    if -1.0 <= x <= 1.0:
        return (x + 1.0) / 2.0
    # heuristique : clamp fort
    if x > 1.0:
        return 1.0
    if x < 0.0:
        return 0.0
    return 0.0

def get_watchlist_snapshot() -> Dict[str, Any]:
    """
    Retourne un payload heatmap {as_of, cells:[{x,y,v,sym}]}.
    Utilise ta fonction projet si dispo; sinon fallback simple.
    """
    cells: List[Dict[str, Any]] = []
    if FN_WATCHLIST:
        try:
            data = FN_WATCHLIST()  # attendu: dict-like {"BTCUSDT": {...}, ...} ou list de dict
            # dict → items; list → itérer
            if isinstance(data, dict):
                items = list(data.items())
            elif isinstance(data, list):
                # essayer de trouver 'symbol'/'sym'
                items = []
                for i, row in enumerate(data):
                    sym = row.get("symbol") or row.get("sym") or row.get("pair") or f"S{i}"
                    items.append((sym, row))
            else:
                items = []
            # construire les cells
            for idx, (sym, row) in enumerate(items):
                # champs possibles pour score
                score = (
                    row.get("score")
                    or row.get("signal_score")
                    or row.get("strength")
                    or row.get("rsi_norm")
                    or 0.0
                )
                v = _normalize_score(score)
                cells.append({"x": idx, "y": 0, "v": round(v, 3), "sym": sym})
        except Exception as e:
            print("[adapter] watchlist error:", e)

    if not cells:
        # Fallback minimal (3 symboles) si aucune data réelle
        base = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        for i, sym in enumerate(base):
            cells.append({"x": i, "y": 0, "v": 0.5, "sym": sym})

    return {"as_of": now_iso(), "cells": cells}

# -----------------------------------------------------------------------------
# Normalisation SIGNAUX
# -----------------------------------------------------------------------------
def get_signals_snapshot() -> List[Dict[str, Any]]:
    """
    Retourne une liste de signaux normalisés:
      [{ts, sym, side: BUY/SELL, score: float, entry: float, strat?: str}, ...]
    """
    out: List[Dict[str, Any]] = []
    if FN_SIGNALS:
        try:
            sigs = FN_SIGNALS()  # attendu: list de dict
            if isinstance(sigs, list):
                for s in sigs:
                    side = (s.get("side") or s.get("signal") or s.get("action") or "").upper()
                    if side not in ("BUY", "SELL"):
                        side = "BUY" if float(s.get("score", 0)) >= 0 else "SELL"
                    out.append({
                        "ts": s.get("ts") or now_iso(),
                        "sym": s.get("symbol") or s.get("sym") or s.get("pair") or "?",
                        "side": side,
                        "score": float(s.get("score", 0.0)),
                        "entry": float(s.get("entry", s.get("price", 0.0))),
                        "strat": s.get("strategy") or s.get("strat") or None,
                    })
        except Exception as e:
            print("[adapter] signals error:", e)
    return out
