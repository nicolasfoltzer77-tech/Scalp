#!/usr/bin/env python3
import os

PAIRS_FILE = os.environ.get("PAIRS_FILE", "/opt/scalp/config/pairs.txt")

def load_pairs():
    pairs = []
    try:
        with open(PAIRS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    pairs.append(s)
    except FileNotFoundError:
        # file absent -> fallback sur top 5
        pairs = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
    return pairs
