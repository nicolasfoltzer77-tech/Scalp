#!/usr/bin/env python3
from __future__ import annotations
import os, json, time, glob

# Répertoires
BASE = "/opt/scalp"
KLINES_DIR = f"{BASE}/data/klines"
OUT_JSON   = f"{BASE}/var/dashboard/data_status.json"

# ↓↓↓ Seuils assouplis ↓↓↓
# nb mini de bougies pour considérer “complet”
REQ_CANDLES = {
    "1m": 600,
    "5m": 600,
    "15m": 600,
}

# fraicheur max (âge du dernier point) pour “fresh”
FRESH_MAX_AGE = {
    "1m": 75,        # 1m frais si < 75 s
    "5m": 4 * 60,    # 5m frais si < 4 min
    "15m": 11 * 60,  # 15m frais si < 11 min
}

# au-delà de ce seuil on bascule “stale”
STALE_AGE = {
    "1m": 5 * 60,     # 5 min
    "5m": 30 * 60,    # 30 min
    "15m": 2 * 60*60, # 2 h
}

TF_ORDER = ["1m", "5m", "15m"]  # priorité basse → haute

def count_rows(csv_path: str) -> int:
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            # fichiers klines → 1 ligne par bougie
            return sum(1 for _ in f)
    except Exception:
        return 0

def last_age_seconds(path: str) -> float:
    try:
        mtime = os.path.getmtime(path)
        return max(0.0, time.time() - mtime)
    except Exception:
        return 1e9

def status_for_file(csv_path: str, tf: str) -> str:
    if not os.path.exists(csv_path):
        return "absent"
    rows = count_rows(csv_path)
    age  = last_age_seconds(csv_path)
    if rows < REQ_CANDLES.get(tf, 600):
        # On a des données mais pas assez → downloading / rattrapage
        return "reloading"
    if age <= FRESH_MAX_AGE.get(tf, 60):
        return "fresh"
    if age >= STALE_AGE.get(tf, 3600):
        return "stale"
    return "reloading"

def main() -> None:
    # construit symbol -> tf -> status
    # On lit *uniquement* ce qu’on trouve dans KLINES_DIR
    symbols = {}
    for tf in TF_ORDER:
        for p in glob.glob(os.path.join(KLINES_DIR, f"*_{tf}.csv")):
            base = os.path.basename(p)
            sym = base.rsplit("_", 1)[0]  # SYMBOL_tf.csv → SYMBOL
            symbols.setdefault(sym, {})
            symbols[sym][tf] = status_for_file(p, tf)

    # Applique la contrainte de priorité :
    # si 1m n’est pas "fresh", 5m et 15m ne peuvent pas être "fresh".
    for sym, m in symbols.items():
        low = m.get("1m", "absent")
        if low != "fresh":
            if m.get("5m") == "fresh":   m["5m"]  = "reloading"
            if m.get("15m") == "fresh":  m["15m"] = "reloading"
        # même idée entre 5m et 15m
        mid = m.get("5m", "absent")
        if mid != "fresh":
            if m.get("15m") == "fresh":  m["15m"] = "reloading"

    out = {
        "ts": int(time.time()),
        "tf_order": TF_ORDER,
        "req_candles": REQ_CANDLES,
        "fresh_max_age": FRESH_MAX_AGE,
        "stale_age": STALE_AGE,
        "items": [{"symbol": s, **symbols[s]} for s in sorted(symbols.keys())],
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    tmp = OUT_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, OUT_JSON)

if __name__ == "__main__":
    main()
