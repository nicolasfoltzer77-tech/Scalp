# engine/scorer.py
from __future__ import annotations
from dataclasses import dataclass
from math import tanh
from typing import Dict, List, Optional
from pathlib import Path
import statistics as stats

from engine.strategy_loader import load_strategy

@dataclass
class ScorerConfig:
    w_ema: float
    w_macd: float
    w_rsi: float
    w_adx: float
    w_obv: float
    buy_th: float
    sell_th: float

def _safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if cur is None: return default
        cur = cur.get(k, None)
    return default if cur is None else cur

def _normalize(x: float, lo: float, hi: float) -> float:
    if hi == lo: return 0.5
    v = (x - lo) / (hi - lo)
    return max(0.0, min(1.0, v))

def _norm_tanh(x: float, t: float = 1.0) -> float:
    # map (-inf, inf) -> (0..1)
    return 0.5 * (tanh(x / max(1e-9, t)) + 1.0)

def _ema(values: List[float], period: int) -> List[float]:
    if not values or period <= 1: return values or []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(out[-1] + k * (v - out[-1]))
    return out

def _atr_from_ohlc(ohlc: List[dict], period: int = 14) -> float:
    # ohlc: list of {"h":..,"l":..,"c":..}
    if len(ohlc) < 2: return 0.0
    trs = []
    prev_c = ohlc[0]["c"]
    for b in ohlc[1:]:
        h, l, c = b["h"], b["l"], b["c"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
        prev_c = c
    return sum(trs[-period:]) / max(1, min(period, len(trs)))

class Scorer:
    """
    Traduit tes "métriques de sélection" + (optionnel) barres 1s -> score [0..1]
    Utilise les poids du JSON stratégie pour rester aligné avec les règles.
    """
    def __init__(self, strategy_path: Path = Path("config/strategy.json")):
        cfg = load_strategy(strategy_path)
        raw = cfg["raw"]
        r = raw["regime_layer"]["indicators"]
        self.cfg = ScorerConfig(
            w_ema   = float(r["ema"]["weight"]),
            w_macd  = float(r["macd"]["weight"]),
            w_rsi   = float(r["rsi"]["weight"]),
            w_adx   = float(r["adx"]["weight"]),
            w_obv   = float(r["obv"]["weight"]),
            buy_th  = float(raw["outputs"]["signals"]["buy_threshold"]),
            sell_th = float(raw["outputs"]["signals"]["sell_threshold"]),
        )
        # pour l’exagération/écrêtage
        self.temp = float(raw["regime_layer"].get("softmax_temperature", 0.35))

    def score_from_selection(self, selection_metrics: Dict) -> float:
        """
        selection_metrics: dict libre venant de ta couche 1 (exemples de clés usuelles)
          - ema_fast, ema_slow, ema_long  (valeurs)
          - macd, macd_signal, macd_hist
          - rsi
          - adx
          - obv_slope
          - vol_atr_pct (volatilité relative)
        """
        ema_f = selection_metrics.get("ema_fast")
        ema_s = selection_metrics.get("ema_slow")
        ema_l = selection_metrics.get("ema_long")
        macd_hist = selection_metrics.get("macd_hist")
        rsi = selection_metrics.get("rsi")
        adx = selection_metrics.get("adx")
        obv_slope = selection_metrics.get("obv_slope")

        ema_score = 0.5
        if all(v is not None for v in (ema_f, ema_s)):
            # >0: tendance haussière ; <0: baissière -> map tanh
            ema_score = _norm_tanh((ema_f - ema_s) / max(1e-9, abs(ema_s)), self.temp)

        macd_score = 0.5 if macd_hist is None else _norm_tanh(macd_hist, self.temp)
        rsi_score = 0.5 if rsi is None else _normalize(rsi, 20, 80)
        adx_score = 0.5 if adx is None else _normalize(adx, 10, 35)  # 20-25 zone active
        obv_score = 0.5 if obv_slope is None else _norm_tanh(obv_slope, self.temp)

        # pondération
        total_w = sum([self.cfg.w_ema, self.cfg.w_macd, self.cfg.w_rsi, self.cfg.w_adx, self.cfg.w_obv]) or 1.0
        raw_score = (
            self.cfg.w_ema  * ema_score +
            self.cfg.w_macd * macd_score +
            self.cfg.w_rsi  * rsi_score +
            self.cfg.w_adx  * adx_score +
            self.cfg.w_obv  * obv_score
        ) / total_w

        # petite pénalité si vol trop faible (porte ATR)
        vol_atr_pct = selection_metrics.get("vol_atr_pct")  # ATR/prix
        if isinstance(vol_atr_pct, (int,float)):
            # gate: si < 0.1% -> -0.05 ; si > 0.5% -> +0.02
            if vol_atr_pct < 0.001: raw_score -= 0.05
            elif vol_atr_pct > 0.005: raw_score += 0.02

        return max(0.0, min(1.0, raw_score))

    def refine_with_1s(self, score: float, bars_1s: Optional[List[dict]]) -> float:
        """
        bars_1s: liste récente de barres 1s: [{"o":..,"h":..,"l":..,"c":..,"v":..}, ...]
        Raffine le score si impulsion/vol 1s soutenus.
        """
        if not bars_1s or len(bars_1s) < 20:
            return score

        closes = [b["c"] for b in bars_1s]
        ema9 = _ema(closes, 9)
        ema21 = _ema(closes, 21) if len(closes) >= 21 else closes
        mom = (ema9[-1] - ema21[-1]) / max(1e-9, ema21[-1]) if len(ema21) else 0.0
        atr1s = _atr_from_ohlc([{"h":b["h"],"l":b["l"],"c":b["c"]} for b in bars_1s], 14)
        price = closes[-1]
        atr_pct = atr1s / max(1e-9, price)

        boost = 0.0
        if mom > 0:
            boost += _norm_tanh(mom*100, 1.0) * 0.05    # + jusqu’à 0.05
        else:
            boost -= _norm_tanh(-mom*100, 1.0) * 0.05
        if atr_pct > 0.003:  # >0.3%
            boost += 0.02

        return max(0.0, min(1.0, score + boost))
