# engine/pairs/selector.py
from __future__ import annotations
import math, statistics as stats, time
from dataclasses import dataclass
from typing import Any, Iterable, List, Dict, Tuple

@dataclass
class PairMetrics:
    symbol: str
    vol_usd_24h: float     # volume $ 24h (proxy)
    atr_pct_24h: float     # volatilité (ATR% sur close)
    score: float           # score combiné

def _ohlcv_to_atr_pct(rows: List[List[float]]) -> float:
    """rows: [ts,o,h,l,c,v]. Renvoie ATR% moyen ~ 24h (proxy simple)."""
    if not rows:
        return 0.0
    atr_vals: List[float] = []
    for i in range(1, len(rows)):
        o,h,l,c,_ = rows[i][1], rows[i][2], rows[i][3], rows[i][4], rows[i][5] if len(rows[i])>5 else 0.0
        pc = rows[i-1][4]
        tr = max(h-l, abs(h-pc), abs(l-pc))
        if c:
            atr_vals.append(tr / c)
    if not atr_vals:
        return 0.0
    return float(sum(atr_vals)/len(atr_vals))

def _norm(vals: List[float]) -> List[float]:
    if not vals: return []
    lo, hi = min(vals), max(vals)
    if hi <= 0 or hi == lo:
        return [0.0 for _ in vals]
    return [(v - lo)/(hi - lo) for v in vals]

def select_top_pairs(
    exchange: Any,
    *,
    universe: Iterable[str] | None = None,
    timeframe: str = "5m",
    lookback_candles: int = 300,   # ~ 24h en 5m
    top_n: int = 10,
    vol_weight: float = 0.6,
    volat_weight: float = 0.4,
) -> List[PairMetrics]:
    """
    Récupère OHLCV pour chaque symbole du 'universe' (sinon via tickers),
    calcule volume USD et ATR% 24h, puis score = 0.6*norm(volume) + 0.4*norm(volatilité).
    Retourne le Top N.
    """
    # 1) Construire l’univers
    symbols: List[str]
    if universe:
        symbols = list(dict.fromkeys([s.replace("_","").upper() for s in universe]))
    else:
        # essaie via exchange.get_ticker() (liste complète)
        try:
            data = exchange.get_ticker().get("data") or []
            symbols = [str(d.get("symbol","")).replace("_","").upper() for d in data if d.get("symbol")]
        except Exception:
            symbols = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","LTCUSDT","LINKUSDT","MATICUSDT"]

    # 2) Collecte OHLCV + proxies volume
    metrics: List[Tuple[str, float, float]] = []  # (symbol, vol_usd, atr_pct)
    for sym in symbols:
        try:
            ohlcv = exchange.get_klines(sym, interval=timeframe, limit=lookback_candles).get("data") or []
            if len(ohlcv) < 50:
                continue
            atr_pct = _ohlcv_to_atr_pct(ohlcv)
            # proxy volume $ : somme(close*volume)
            vol_usd = 0.0
            for r in ohlcv[-288:]:  # ~ dernier jour
                close = float(r[4]); vol = float(r[5]) if len(r)>5 else 0.0
                vol_usd += close * vol
            metrics.append((sym, vol_usd, atr_pct))
        except Exception:
            continue

    if not metrics:
        return []

    vols = [m[1] for m in metrics]
    vols_norm = _norm(vols)
    atrs = [m[2] for m in metrics]
    atrs_norm = _norm(atrs)

    scored: List[PairMetrics] = []
    for (sym, vol_usd, atr_pct), nv, na in zip(metrics, vols_norm, atrs_norm):
        s = vol_weight*nv + volat_weight*na
        scored.append(PairMetrics(symbol=sym, vol_usd_24h=vol_usd, atr_pct_24h=atr_pct, score=s))

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:top_n]