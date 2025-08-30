# -*- coding: utf-8 -*-
"""
Runner de stratégies minimal, robuste et sans dépendances lourdes.
Indicateurs: SMA, EMA, RSI + logique de combinaison "majority/any/all".
OHLCV attendu dans: /opt/scalp/data/<SY>/<TF>/ohlcv.json
Format OHLCV: liste de [ts, open, high, low, close, volume] (ts en ms)
"""

from __future__ import annotations
import json, math, os
from pathlib import Path
from typing import Dict, Any, List, Tuple

# --- Utils numériques (numpy-less)
def sma(values: List[float], length: int) -> List[float]:
    if length <= 0: return []
    out: List[float] = []
    acc = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= length: acc -= values[i-length]
        out.append(acc/length if i+1 >= length else math.nan)
    return out

def ema(values: List[float], length: int) -> List[float]:
    if length <= 0: return []
    alpha = 2.0 / (length + 1.0)
    out: List[float] = []
    last = None
    for v in values:
        if last is None:
            last = v
        else:
            last = alpha * v + (1.0 - alpha) * last
        out.append(last)
    # préfixer de nan jusqu'à avoir "plein"
    prefix = [math.nan] * (length - 1)
    return prefix + out[len(prefix):]

def rsi(values: List[float], length: int) -> List[float]:
    if length <= 0: return []
    gains = [0.0]; losses = [0.0]
    for i in range(1, len(values)):
        chg = values[i] - values[i-1]
        gains.append(max(chg, 0.0))
        losses.append(max(-chg, 0.0))
    avg_g = sma(gains, length)
    avg_l = sma(losses, length)
    out: List[float] = []
    for g,l in zip(avg_g, avg_l):
        if math.isnan(g) or math.isnan(l) or l == 0:
            out.append(100.0 if l == 0 and not math.isnan(g) else math.nan)
        else:
            rs = g / l
            out.append(100.0 - 100.0 / (1.0 + rs))
    return out

# --- Chargement config
def load_strategies(yaml_path: str = "/opt/scalp/engine/strategies/strategies.yaml") -> Dict[str, Any]:
    import yaml
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"strategies.yaml introuvable: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))

# --- Data loader
def load_ohlcv(symbol: str, tf: str, data_dir: str = "/opt/scalp/data") -> List[List[float]]:
    p = Path(data_dir) / symbol / tf / "ohlcv.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []

# --- Évaluation d’une stratégie sur un close[]
def eval_single_rule(closes: List[float], rule: Dict[str, Any]) -> str:
    t = (rule.get("type") or "").lower()
    if t == "sma_cross":
        fast = int(rule.get("fast", 9))
        slow = int(rule.get("slow", 21))
        bias = (rule.get("bias") or "both").lower()
        sf = sma(closes, fast)
        ss = sma(closes, slow)
        if len(closes) < max(fast, slow) + 2: return "HOLD"
        # signal = croisement sur les 2 dernières barres
        a1, b1 = sf[-2], ss[-2]
        a2, b2 = sf[-1], ss[-1]
        if any(map(math.isnan, [a1,b1,a2,b2])): return "HOLD"
        # croisement up: BUY ; down: SELL
        if a1 <= b1 and a2 > b2 and bias in ("both","long"):
            return "BUY"
        if a1 >= b1 and a2 < b2 and bias in ("both","short"):
            return "SELL"
        return "HOLD"

    if t == "ema_trend":
        fast = int(rule.get("fast", 50))
        slow = int(rule.get("slow", 200))
        momentum_min = float(rule.get("momentum_min", 0.0))
        ef = ema(closes, fast)
        es = ema(closes, slow)
        if len(closes) < max(fast, slow) + 1: return "HOLD"
        c1, c2 = closes[-2], closes[-1]
        f2, s2 = ef[-1], es[-1]
        if any(map(math.isnan, [f2, s2])): return "HOLD"
        mom = 0.0 if c1 == 0 else (c2 - c1) / max(abs(c1), 1e-9)
        if f2 > s2 and mom >= momentum_min:
            return "BUY"
        if f2 < s2 and (-mom) >= momentum_min:
            return "SELL"
        return "HOLD"

    if t == "rsi":
        length = int(rule.get("length", 14))
        oversold = float(rule.get("oversold", 30))
        overbought = float(rule.get("overbought", 70))
        confirm = int(rule.get("confirmation", 1))
        rv = rsi(closes, length)
        if len(rv) < max(length+confirm, 3): return "HOLD"
        r_prev = rv[-(confirm+1)]
        r_now  = rv[-1]
        if math.isnan(r_prev) or math.isnan(r_now): return "HOLD"
        if r_prev < oversold and r_now > r_prev:
            return "BUY"
        if r_prev > overbought and r_now < r_prev:
            return "SELL"
        return "HOLD"

    # inconnu => neutre
    return "HOLD"

def eval_strategy(ohlcv: List[List[float]], strat_cfg: Dict[str, Any]) -> str:
    if not ohlcv or len(ohlcv) < 5:
        return "HOLD"
    closes = [float(x[4]) for x in ohlcv if isinstance(x, list) and len(x) >= 5]
    res = "HOLD"
    for rule in strat_cfg.get("rules", []):
        sig = eval_single_rule(closes, rule)
        # simple: si une règle donne BUY/SELL, on la remonte (les règles sont déjà "cohérentes")
        if sig != "HOLD":
            res = sig
    return res

def combine(signals: List[str], mode: str = "majority", min_votes: int = 1) -> str:
    b = sum(1 for s in signals if s == "BUY")
    s = sum(1 for s in signals if s == "SELL")
    if mode == "all-buy":
        return "BUY" if b == len(signals) and b >= min_votes else "HOLD"
    if mode == "any-buy":
        return "BUY" if b >= min_votes else "HOLD"
    # majority
    if b >= max(s, 0) and b >= min_votes and b > 0:
        return "BUY"
    if s > b and s > 0:
        return "SELL"
    return "HOLD"

def evaluate_for(symbol: str, cfg: Dict[str, Any], data_dir: str = "/opt/scalp/data") -> Tuple[str, Dict[str, str]]:
    signals: List[str] = []
    details: Dict[str, str] = {}
    for st in cfg.get("strategies", []):
        tf = st.get("tf") or "1m"
        ohlcv = load_ohlcv(symbol, tf, data_dir=data_dir)
        sig = eval_strategy(ohlcv, st)
        signals.append(sig)
        details[f"{st.get('name','?')}@{tf}"] = sig
    comb = combine(signals, mode=(cfg.get("combine", {}).get("mode") or "majority"),
                   min_votes=int(cfg.get("combine", {}).get("min_votes") or 1))
    return comb, details

# CLI simple (debug)
if __name__ == "__main__":
    import sys, yaml
    if len(sys.argv) < 2:
        print("Usage: runner.py SYMBOL [DATA_DIR]")
        sys.exit(0)
    sy = sys.argv[1].upper()
    data_dir = sys.argv[2] if len(sys.argv) > 2 else "/opt/scalp/data"
    cfg = load_strategies()
    comb, details = evaluate_for(sy, cfg, data_dir)
    print(f"symbol={sy} -> combined={comb}")
    for k,v in details.items():
        print(f"  {k}: {v}")
