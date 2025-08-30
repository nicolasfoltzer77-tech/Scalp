#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Met à jour /opt/scalp/config/pairs.txt avec un TOP N (volume/volatilité)
en conservant un noyau dur de paires (BTC/ETH/BNB/SOL/XRP).

- Source: API publique Binance /api/v3/ticker/24hr (pas de clé nécessaire)
- Filtre: symboles se terminant par USDT
- Score:  w_volume * quoteVolume_USDT  +  w_volatilite * abs(priceChangePercent)
- N max configurable via env TOPN (par défaut 20)
"""

import os, sys, time, json
from typing import List, Dict, Any
import requests

PAIRS_FILE = os.environ.get("PAIRS_FILE", "/opt/scalp/config/pairs.txt")
PINNED = os.environ.get("PINNED", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT").split(",")
TOPN   = int(os.environ.get("TOPN", "20"))
W_VOL  = float(os.environ.get("W_VOLUME", "1.0"))
W_VAR  = float(os.environ.get("W_VOLAT", "1.0"))

BINANCE_TICKER_24H = "https://api.binance.com/api/v3/ticker/24hr"

def fetch_tickers() -> List[Dict[str, Any]]:
    r = requests.get(BINANCE_TICKER_24H, timeout=15)
    r.raise_for_status()
    return r.json()

def score_row(row: Dict[str, Any]) -> float:
    try:
        qv = float(row.get("quoteVolume", "0"))  # en USDT pour les paires ***USDT
        pct = abs(float(row.get("priceChangePercent", "0")))
        return W_VOL * qv + W_VAR * pct
    except Exception:
        return 0.0

def compute_top(tickers: List[Dict[str, Any]], pinned: List[str], topn: int) -> List[str]:
    # garde uniquement les paires se terminant par USDT
    usdt = [t for t in tickers if isinstance(t.get("symbol"), str) and t["symbol"].endswith("USDT")]
    # ordonne par score
    usdt.sort(key=score_row, reverse=True)
    # construit la liste finale
    out: List[str] = []
    # commence par les pinned (si existants dans la liste globale)
    for p in pinned:
        if p not in out:
            out.append(p)
    # complète avec le top scoré
    for row in usdt:
        s = row["symbol"]
        if s not in out:
            out.append(s)
        if len(out) >= topn:
            break
    return out

def write_pairs(pairs: List[str], path: str) -> None:
    # fichier final sans doublons, une ligne par paire
    uniq = []
    for p in pairs:
        if p not in uniq:
            uniq.append(p)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(uniq) + "\n")

def main() -> int:
    try:
        tickers = fetch_tickers()
        pairs = compute_top(tickers, PINNED, TOPN)
        write_pairs(pairs, PAIRS_FILE)
        print(f"[update_pairs] Ecrit {len(pairs)} paires -> {PAIRS_FILE}")
        return 0
    except Exception as e:
        print(f"[update_pairs] ERREUR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
