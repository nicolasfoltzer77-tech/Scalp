#!/usr/bin/env python3
from __future__ import annotations
import csv, os, time
from typing import Dict, Any

BASE = "/opt/scalp/var/dashboard"
CSV  = f"{BASE}/signals_f.csv"

HEADER = [
    "ts","symbol","tf",
    "signal",               # BUY/SELL/HOLD (combiné)
    "score",                # somme factorisée
    # composantes (brut et facteur)
    "rsi_value","rsi_factor",
    "ema_gap","ema_factor",
    "sma_cross_fast","sma_factor",
    # trace libre
    "details"
]

def _to_int(v, default=0):
    try: return int(v)
    except: return default

def _to_float(v, default=0.0):
    try: return float(v)
    except: return default

def append_signal_factored(row: Dict[str, Any]) -> None:
    """
    row attendu au minimum:
      symbol, tf, signal (BUY/SELL/HOLD)
    et si dispo (facultatif): rsi_value, ema_gap, sma_cross_fast, rsi_factor, ema_factor, sma_factor, score, details
    -> crée BASE si besoin, écrit l'entête si nouveau fichier.
    """
    os.makedirs(BASE, exist_ok=True)
    write_header = not os.path.exists(CSV)

    ts = _to_int(row.get("ts") or time.time(), int(time.time()))
    symbol = (row.get("symbol") or "").strip()
    tf = (row.get("tf") or "").strip()
    signal = (row.get("signal") or "HOLD").strip().upper()

    # valeurs brutes (si non fournies on met 0)
    rsi_value = _to_float(row.get("rsi_value"), 0.0)
    ema_gap   = _to_float(row.get("ema_gap"), 0.0)       # ex: (price-ema)/ema
    sma_cross_fast = (row.get("sma_cross_fast") or "").upper()  # "BUY"/"SELL"/"HOLD"

    # facteurs (+1/0/-1) – si absents on les déduit de règles simples
    def sign(x: float) -> int:
        return 1 if x > 0 else (-1 if x < 0 else 0)

    rsi_factor = int(row.get("rsi_factor")) if str(row.get("rsi_factor")).lstrip("+-").isdigit() else (
        1 if 55 <= rsi_value <= 70 else (-1 if 30 <= rsi_value <= 45 else 0)
    )
    ema_factor = int(row.get("ema_factor")) if str(row.get("ema_factor")).lstrip("+-").isdigit() else sign(ema_gap)
    sma_factor = int(row.get("sma_factor")) if str(row.get("sma_factor")).lstrip("+-").isdigit() else (
        1 if sma_cross_fast == "BUY" else (-1 if sma_cross_fast == "SELL" else 0)
    )

    # score
    score = row.get("score")
    if score is None:
        try:
            score = int(rsi_factor) + int(ema_factor) + int(sma_factor)
        except:
            score = 0

    details = (row.get("details") or "").strip()[:512]

    out = {
        "ts": ts, "symbol": symbol, "tf": tf,
        "signal": signal,
        "score": int(score),
        "rsi_value": rsi_value, "rsi_factor": int(rsi_factor),
        "ema_gap": ema_gap, "ema_factor": int(ema_factor),
        "sma_cross_fast": sma_cross_fast, "sma_factor": int(sma_factor),
        "details": details
    }

    # écriture
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        if write_header:
            w.writeheader()
        w.writerow(out)
