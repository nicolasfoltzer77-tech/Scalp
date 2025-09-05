#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy_bridge.py
- Point d'entrée unique pour évaluer une (symbol, tf)
- Fournit toujours un dict avec:
    {
      "combined": "BUY/SELL/HOLD",
      "items": [ {"name": "...", "signal": "BUY/SELL/HOLD", "value": <opt>} , ... ],
      "metrics": { "rsi": float|None, "ema": float|None, "sma": float|None },
    }
- Essaie de calculer les métriques si elles ne sont pas fournies par la stratégie:
  1) utilise res["metrics"] si présent
  2) calcule depuis ohlcv passé en param
  3) sinon récupère 100 bougies chez Binance et calcule
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import math, time, logging, json

try:
    import requests  # utilisé uniquement en fallback (pas bloquant si absent)
except Exception:
    requests = None  # type: ignore

LOG = logging.getLogger("strategy_bridge")

# ---------------------------- utils indicateurs ---------------------------- #

def _ema(values: List[float], period: int) -> Optional[float]:
    if not values or len(values) < period:
        return None
    k = 2.0 / (period + 1.0)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return float(ema)

def _sma(values: List[float], period: int) -> Optional[float]:
    if not values or len(values) < period:
        return None
    return float(sum(values[-period:]) / period)

def _rsi(values: List[float], period: int = 14) -> Optional[float]:
    if not values or len(values) <= period:
        return None
    gains, losses = 0.0, 0.0
    # premières diff pour init
    for i in range(1, period + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    # lissage Wilder
    for i in range(period + 1, len(values)):
        diff = values[i] - values[i - 1]
        gain = max(diff, 0.0)
        loss = max(-diff, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return float(rsi)

def _closes_from_ohlcv(ohlcv: Optional[List[List[float]]]) -> Optional[List[float]]:
    if not ohlcv:
        return None
    closes: List[float] = []
    for row in ohlcv:
        if not row or len(row) < 5:
            continue
        try:
            closes.append(float(row[4]))
        except Exception:
            continue
    return closes or None

# ------------------------- fallback fetch OHLCV (Binance) ------------------ #

_BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

def _binance_tf(tf: str) -> str:
    # compat rapide
    return {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h"}.get(tf, tf)

def _fetch_ohlcv_binance(symbol: str, tf: str, limit: int = 100) -> Optional[List[List[float]]]:
    if requests is None:
        return None
    try:
        params = {"symbol": symbol.upper(), "interval": _binance_tf(tf), "limit": max(50, min(limit, 1000))}
        r = requests.get(_BINANCE_KLINES, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        ohlcv: List[List[float]] = []
        for k in data:
            # open time, open, high, low, close, volume, close time, ...
            ohlcv.append([float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[4])])
        return ohlcv
    except Exception as e:
        LOG.debug("binance fallback failed: %s", e)
        return None

# ----------------------------- coeur stratégie ----------------------------- #

def _run_strategies(symbol: str, tf: str, strategies: List[Dict[str, Any]],
                    config: Dict[str, Any], logger: Optional[logging.Logger]) -> Dict[str, Any]:
    """
    Cette fonction représente l'existant : on suppose que tes stratégies
    retournent au minimum:
      - 'combined'  (BUY/SELL/HOLD)
      - 'items'     (liste de sous-signaux)
    Si elles ajoutent déjà 'metrics', on le respecte.
    """
    # ⚠️ Exemple fictif si tes stratégies appellent déjà une librairie maison.
    # Remplace ce bloc par l'appel réel si besoin.
    try:
        from engine.strategies.runner import evaluate_for as _real_eval   # type: ignore
        return _real_eval(symbol=symbol, tf=tf, strategies=strategies, config=config, logger=logger)
    except Exception:
        # Fallback minimal si runner interne n'expose pas evaluate_for
        return {"combined": "HOLD", "items": []}

def _ensure_metrics(res: Dict[str, Any], symbol: str, tf: str,
                    ohlcv: Optional[List[List[float]]]) -> Dict[str, Any]:
    """Complète res['metrics'] si absent, via ohlcv fourni ou récupéré."""
    if "metrics" in res and isinstance(res["metrics"], dict):
        # normalise types
        m = res["metrics"]
        res["metrics"] = {
            "rsi": float(m.get("rsi")) if m.get("rsi") is not None else None,
            "ema": float(m.get("ema")) if m.get("ema") is not None else None,
            "sma": float(m.get("sma")) if m.get("sma") is not None else None,
        }
        return res

    closes = _closes_from_ohlcv(ohlcv)
    if closes is None:
        # tente un fetch léger si rien n'a été fourni
        fetched = _fetch_ohlcv_binance(symbol, tf, limit=100)
        closes = _closes_from_ohlcv(fetched)

    rsi = _rsi(closes, 14) if closes else None
    ema = _ema(closes, 20) if closes else None
    sma = _sma(closes, 20) if closes else None
    res["metrics"] = {"rsi": rsi, "ema": ema, "sma": sma}
    return res

def evaluate_for(*, symbol: str, tf: str,
                 strategies: List[Dict[str, Any]], config: Dict[str, Any],
                 ohlcv: Optional[List[List[float]]] = None,
                 logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    API utilisée par le scheduler.
    Garantit la présence de res['metrics'].
    """
    logger = logger or LOG
    base = _run_strategies(symbol, tf, strategies, config, logger)

    # garde fou sur la structure
    combined = str(base.get("combined", "HOLD")).upper()
    items = base.get("items") or []
    if not isinstance(items, list):
        items = []

    res = {"combined": combined, "items": items}
    # copie éventuelle d'autres clés utiles
    for k in ("context", "extra", "ohlcv"):
        if k in base:
            res[k] = base[k]

    res = _ensure_metrics(res, symbol, tf, ohlcv or base.get("ohlcv"))  # type: ignore[arg-type]
    return res
