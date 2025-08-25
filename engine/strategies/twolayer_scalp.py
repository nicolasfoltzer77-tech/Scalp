#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TwoLayer_Scalp — couche régime multi‑TF + couche entrées paramétrables.
Supporte:
  - JSON unique (héritage) OU 2 JSON scindés (recommandé).

Expose:
  - load_combined_or_split(schema_json, schema_backtest_json, schema_entries_json)
  - compute_regime_score_multi_tf(df_by_tf, schema_backtest)
  - build_entries_frame(df_entry_tf, schema_entries)
  - run_backtest_exec(df_exec, p_buy, schema_backtest, schema_entries)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import math, json
import numpy as np
import pandas as pd

# -------- Indicateurs compacts (pas de dépendances exotiques) ----------
def ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False).mean()

def macd(s: pd.Series, fast=12, slow=26, signal=9):
    ema_f = ema(s, fast); ema_s = ema(s, slow)
    macd_line = ema_f - ema_s
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def rsi(s: pd.Series, length=14):
    d = s.diff()
    up = d.clip(lower=0.0); dn = -d.clip(upper=0.0)
    roll_up = up.ewm(alpha=1/length, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1/length, adjust=False).mean()
    rs = roll_up / (roll_dn + 1e-12)
    return 100.0 - 100.0 / (1.0 + rs)

def _true_range(df: pd.DataFrame):
    pc = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs()
    ], axis=1).max(axis=1)

def atr(df: pd.DataFrame, length=14):
    return _true_range(df).rolling(length, min_periods=length).mean()

def bbands(s: pd.Series, length=20, std=2.0):
    m = s.rolling(length).mean()
    sd = s.rolling(length).std(ddof=0)
    u = m + std * sd
    l = m - std * sd
    return m, u, l

def vwap(df: pd.DataFrame):
    pv = (df["close"] * df["volume"]).cumsum()
    vv = df["volume"].cumsum().replace(0, np.nan)
    return pv / vv

def keltner(df: pd.DataFrame, length=20, atr_mult=1.5):
    mid = ema(df["close"], length)
    rng = atr(df, length)
    return mid, mid + atr_mult*rng, mid - atr_mult*rng

def obv(df: pd.DataFrame):
    direction = np.sign(df["close"].diff().fillna(0.0))
    return (direction * df["volume"]).fillna(0.0).cumsum()

def adx(df: pd.DataFrame, length=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = _true_range(df)
    atr_n = tr.rolling(length).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(length).sum() / (atr_n*length + 1e-12))
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(length).sum() / (atr_n*length + 1e-12))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-12)) * 100
    return dx.rolling(length).mean().rename("adx")

# -------- Helpers score régime ----------------------------------------
def _tanh_norm(x: pd.Series, win: int = 100) -> pd.Series:
    mu = x.rolling(win).mean()
    sd = x.rolling(win).std(ddof=0)
    z = (x - mu) / (sd + 1e-12)
    return np.tanh(z)

@dataclass
class Costs:
    maker: float
    taker: float
    slip_bps: float

def compute_regime_score_multi_tf(df_by_tf: Dict[str, pd.DataFrame], schema_backtest: Dict) -> pd.Series:
    reg = schema_backtest["regime_layer"]
    inds = reg["indicators"]
    atr_gate = reg.get("atr_gate_thresholds_pct", {})
    norm_kind = reg.get("score_normalization", "tanh")

    # poids par TF
    keys = list(df_by_tf.keys())
    w = np.array([reg["tf_weights"].get(tf, 0.0) for tf in keys], dtype=float)
    w = w / w.sum() if w.sum() > 0 else np.ones_like(w)/max(1, len(w))

    tf_scores = []
    for tf, df in df_by_tf.items():
        ef = ema(df["close"], inds["ema"]["fast"].get(tf, 12))
        es = ema(df["close"], inds["ema"]["slow"].get(tf, 26))
        el = ema(df["close"], inds["ema"]["long"].get(tf, 200))
        _, _, hist = macd(df["close"],
                          inds["macd"]["fast"].get(tf,12),
                          inds["macd"]["slow"].get(tf,26),
                          inds["macd"]["signal"].get(tf,9))
        rsi_v = rsi(df["close"], inds["rsi"]["length"].get(tf,14))
        adx_v = adx(df, reg["indicators"]["adx"]["length"])
        obv_v = obv(df)
        obv_slope = obv_v.diff(reg["indicators"]["obv"]["slope_lookback"]).fillna(0.0)

        f_ema = (ef - es) / (el + 1e-12)
        if norm_kind == "tanh":
            f_ema = _tanh_norm(f_ema, inds["macd"].get("norm_window", 100))
            f_macd = _tanh_norm(hist, inds["macd"].get("norm_window", 100))
            f_rsi  = ((rsi_v - 50.0)/50.0).clip(-1,1)
            f_adx  = (adx_v.fillna(0.0)/100.0).clip(0,1)
            f_obv  = _tanh_norm(obv_slope, reg["indicators"]["obv"]["norm_median_lookback"]).clip(-1,1)
        else:
            f_macd, f_rsi, f_adx, f_obv = hist, (rsi_v-50)/50, adx_v/100.0, obv_slope

        w_ema = inds["ema"]["weight"]; w_macd = inds["macd"]["weight"]
        w_rsi = inds["rsi"]["weight"]; w_adx  = inds["adx"]["weight"]
        w_obv = inds["obv"]["weight"]
        score = w_ema*f_ema + w_macd*f_macd + w_rsi*f_rsi + w_adx*f_adx + w_obv*f_obv

        a = atr(df).fillna(method="ffill")
        gate = (a / (df["close"] + 1e-12) >= atr_gate.get(tf, 0.0)).astype(float)
        tf_scores.append(score * gate)

    M = pd.concat(tf_scores, axis=1).fillna(method="ffill")
    M.columns = keys
    raw = (M * w).sum(axis=1)
    p_buy = (raw.clip(-1,1) + 1.0) / 2.0
    return p_buy.clip(0,1)

def hysteresis_state(p_buy: pd.Series, hyst: Dict[str, float]) -> pd.Series:
    buy_on = hyst["buy_on_above"]; buy_exit = hyst["buy_exit_below"]
    sell_on = hyst.get("sell_on_above", buy_on); sell_exit = hyst.get("sell_exit_below", buy_exit)
    st = 0
    out = []
    for v in p_buy.fillna(0.0).values:
        if st >= 0:
            if v >= buy_on: st = 1
            elif v <= buy_exit: st = 0
        if st <= 0:
            if v <= (1 - sell_on): st = -1
            elif v >= (1 - sell_exit): st = 0
        out.append(st)
    return pd.Series(out, index=p_buy.index)

# -------- Entrées sets --------------------------------------------------
def _entry_pullback_trend(df: pd.DataFrame, common: Dict, spec: Dict) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["ema20"] = ema(df["close"], 20)
    vwp = vwap(df)
    bbm, bbu, bbl = bbands(df["close"], common["bbands"]["length"], common["bbands"]["stddev"])
    rsi_len = spec["signals"]["rsi_cross"]["length"]; lvl = spec["signals"]["rsi_cross"]["level"]
    rsi_v = rsi(df["close"], rsi_len); rsi_prev = rsi_v.shift(1)
    touch = (df["low"] <= out["ema20"]) | (df["low"] <= vwp) | (df["low"] <= bbl)
    rsi_cross_up = (rsi_prev < lvl) & (rsi_v >= lvl)
    body = (df["close"] - df["open"]).abs()
    body_ok = body >= body.rolling(50).median()
    if not spec["signals"].get("candle_body_above_median", True):
        body_ok = pd.Series(True, index=df.index)
    cond = touch & rsi_cross_up & body_ok
    out["entry_long"] = cond.astype(int)
    a = atr(df, 14)
    out["sl"] = df["close"] - spec["risk"]["sl_atr_mult"] * a
    out["tp"] = df["close"] + spec["risk"]["tp_atr_mult"] * a
    out["entry_set"] = "pullback_trend"
    return out[["entry_long","sl","tp","entry_set"]]

def _entry_breakout(df: pd.DataFrame, common: Dict, spec: Dict) -> pd.DataFrame:
    n = spec["signals"]["close_above_high_n"]
    hh = df["high"].rolling(n).max().shift(1)
    _, _, hist = macd(df["close"])
    macd_up = hist > hist.shift(1)
    bbm, bbu, bbl = bbands(df["close"], common["bbands"]["length"], common["bbands"]["stddev"])
    km, ku, kl = keltner(df, common["keltner"]["length"], common["keltner"]["atr_mult"])
    inside = (bbu < ku) & (bbl > kl); expand = (bbu > ku) & (bbl < kl)
    squeeze_ok = inside.shift(1).fillna(False) & expand.fillna(False)
    cond = (df["close"] > hh) & macd_up & squeeze_ok
    out = pd.DataFrame(index=df.index)
    out["entry_long"] = cond.astype(int)
    a = atr(df, 14)
    rl = df["low"].rolling(n).min().shift(1)
    if spec["risk"].get("sl_method","") == "below_range_n_low":
        out["sl"] = rl
    else:
        out["sl"] = df["close"] - spec["risk"].get("sl_atr_mult", 1.0) * a
    if spec["risk"].get("tp_method","") in ("range_height_or_atr",):
        rh = (df["high"].rolling(n).max().shift(1) - df["low"].rolling(n).min().shift(1)).abs()
        out["tp"] = df["close"] + np.maximum(rh, spec["risk"].get("tp_atr_mult",1.5)*a)
    else:
        out["tp"] = df["close"] + spec["risk"].get("tp_atr_mult",1.5)*a
    out["entry_set"] = "breakout"
    return out[["entry_long","sl","tp","entry_set"]]

_ENTRY_DISPATCH = {
    "pullback_trend": _entry_pullback_trend,
    "breakout": _entry_breakout,
}

def build_entries_frame(df_entry_tf: pd.DataFrame, schema_entries: Dict) -> pd.DataFrame:
    sets = schema_entries["entry_layer"]["sets"]; common = schema_entries["entry_layer"]["common"]
    parts = []
    for name in sets.keys():
        if name in _ENTRY_DISPATCH:
            parts.append(_ENTRY_DISPATCH[name](df_entry_tf, common, sets[name]))
    if not parts:
        return pd.DataFrame(index=df_entry_tf.index, data={"entry_long":0,"sl":np.nan,"tp":np.nan,"entry_set":""})
    out = pd.DataFrame(index=df_entry_tf.index)
    out["entry_long"] = pd.concat([p["entry_long"] for p in parts], axis=1).max(axis=1).astype(int)
    out["sl"] = parts[0]["sl"]; out["tp"] = parts[0]["tp"]
    first = []
    for i in range(len(df_entry_tf)):
        tag = ""
        for p in parts:
            if int(p["entry_long"].iloc[i]) == 1:
                tag = str(p["entry_set"].iloc[0]) if "entry_set" in p.columns else ""
                break
        first.append(tag)
    out["entry_set"] = first
    return out

# -------- Backtest exécution -------------------------------------------
def hysteresis_state_series(p_buy: pd.Series, schema_backtest: Dict) -> pd.Series:
    return hysteresis_state(p_buy, schema_backtest["regime_layer"]["hysteresis"])

def run_backtest_exec(df_exec: pd.DataFrame, p_buy: pd.Series, schema_backtest: Dict, schema_entries: Dict) -> Dict:
    state = hysteresis_state_series(p_buy, schema_backtest)
    timeout_bars = schema_entries["entry_layer"]["common"]["timeout_bars"]
    maker = schema_backtest["costs"].get("maker_fee_rate", 0.0002)
    taker = schema_backtest["costs"].get("taker_fee_rate", 0.0008)
    slip = schema_backtest["costs"].get("slippage_max_bps", 5.0) / 10000.0
    prefer_maker = schema_entries.get("execution", {}).get("prefer_maker", True)
    allow_market_on_breakout = schema_entries.get("execution", {}).get("allow_market_on_breakout", True)
    risk_pct = schema_backtest["risk_management"]["position_sizing"]["risk_pct_per_trade"]

    in_pos = False; entry_px = 0.0; sl = np.nan; tp = np.nan
    eq = 1.0; curve = [eq]; rets = []; bars = 0

    for i in range(len(df_exec)):
        c = df_exec["close"].iloc[i]; hi = df_exec["high"].iloc[i]; lo = df_exec["low"].iloc[i]
        sig = int(df_exec["entry_long"].iloc[i]) if "entry_long" in df_exec else 0
        st = int(state.iloc[i])

        if in_pos:
            bars += 1
            hit_tp = hi >= tp; hit_sl = lo <= sl; timeout = bars >= timeout_bars
            if hit_tp or hit_sl or timeout or (st <= 0):
                fee = taker
                exit_px = tp if hit_tp else (sl if hit_sl else c)
                exit_px = exit_px * (1 - fee) * (1 - slip)
                r = (exit_px - entry_px) / entry_px
                rets.append(r); eq *= (1 + r * risk_pct); curve.append(eq)
                in_pos = False; bars = 0
                continue

        if (not in_pos) and (st > 0) and (sig == 1):
            fee = maker if prefer_maker else taker
            if allow_market_on_breakout and df_exec.get("entry_set", pd.Series(index=df_exec.index, data="")).iloc[i] == "breakout":
                fee = taker
            entry_px = c * (1 + fee) * (1 + slip)
            sl = df_exec["sl"].iloc[i]; tp = df_exec["tp"].iloc[i]
            in_pos = True; bars = 0

        curve.append(eq)

    trades = len(rets); wins = sum(1 for r in rets if r > 0)
    pf = (sum(r for r in rets if r > 0) / (sum(-r for r in rets if r <= 0) + 1e-12)) if trades else 0.0
    wr = wins / trades if trades else 0.0
    arr = np.array(curve, dtype=float); roll = np.maximum.accumulate(arr)
    dd = (arr - roll) / (roll + 1e-12)
    mdd = -dd.min() if len(dd) else 0.0
    if trades > 1:
        mu = float(np.mean(rets)); sd = float(np.std(rets, ddof=1) + 1e-12)
        sharpe = (mu / sd) * math.sqrt(252)
    else:
        sharpe = 0.0
    return {"pf": float(pf), "mdd": float(mdd), "trades": int(trades), "wr": float(wr), "sharpe": float(sharpe), "equity": float(arr[-1])}

# -------- Chargement schémas (avec fallback schemas/) ------------------
def load_combined_or_split(schema_json: Optional[str],
                           schema_backtest_json: Optional[str],
                           schema_entries_json: Optional[str]) -> Tuple[Dict, Dict]:
    """
    Renvoie (schema_backtest, schema_entries)
    Priorité :
      1) schema_json (JSON unique)
      2) schema_backtest_json + schema_entries_json
      3) defaults: <repo_root>/schemas/schema_backtest.json + schema_entries.json
    """
    import os, json as _json
    if schema_json:
        with open(schema_json, "r", encoding="utf-8") as f:
            full = _json.load(f)
        back = {
            "schema_version": full.get("schema_version", ""),
            "strategy_name": full.get("strategy_name", "TwoLayer_Scalp"),
            "assets": full.get("assets", []),
            "timeframes": full.get("timeframes", {}),
            "regime_layer": full.get("regime_layer", {}),
            "risk_management": full.get("risk_management", {}),
            "costs": full.get("costs", {}),
            "backtest": full.get("backtest", {}),
            "optimization": full.get("optimization", {}),
            "outputs": full.get("outputs", {})
        }
        entries = {"entry_layer": full.get("entry_layer", {}), "execution": full.get("execution", {})}
        return back, entries

    if schema_backtest_json and schema_entries_json:
        with open(schema_backtest_json, "r", encoding="utf-8") as f:
            back = _json.load(f)
        with open(schema_entries_json, "r", encoding="utf-8") as f:
            entries = _json.load(f)
        return back, entries

    # Fallback défaut: schemas/ à la racine du repo
    here = os.path.abspath(os.path.dirname(__file__))           # .../engine/strategies
    repo_root = os.path.abspath(os.path.join(here, "..", "..")) # racine repo
    sb_def = os.path.join(repo_root, "schemas", "schema_backtest.json")
    se_def = os.path.join(repo_root, "schemas", "schema_entries.json")
    if os.path.isfile(sb_def) and os.path.isfile(se_def):
        with open(sb_def, "r", encoding="utf-8") as f:
            back = _json.load(f)
        with open(se_def, "r", encoding="utf-8") as f:
            entries = _json.load(f)
        return back, entries

    raise FileNotFoundError(
        "Aucun schéma fourni et fichiers par défaut introuvables. "
        "Place `schemas/schema_backtest.json` et `schemas/schema_entries.json` à la racine, "
        "ou passe --schema-json / --schema-backtest + --schema-entries."
    )