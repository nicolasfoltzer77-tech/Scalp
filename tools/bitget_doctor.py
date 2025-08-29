# -*- coding: utf-8 -*-
"""
Bitget candles doctor (UMCBL).
Essaie plusieurs variantes d'endpoints et de paramètres pour trouver
celle que l'API accepte pour les futures (UMCBL).
"""

import os, json, time
import requests

BASE = "https://api.bitget.com"
SYMBOLS = ["BTCUSDT", "BTCUSDT_UMCBL"]  # on testera les 2, le code ajoutera le suffixe si besoin
MARKET = "umcbl"

# variantes d'endpoints observées dans la doc / SDK
VARIANTS = [
    # (path, params_template, note)
    ("/api/mix/v1/market/candles",          {"granularity": "1min", "limit": 5}, "mix/candles gran=str 1min"),
    ("/api/mix/v1/market/candles",          {"granularity": 60,     "limit": 5}, "mix/candles gran=int 60"),
    ("/api/mix/v1/market/candles",          {"granularity": "1m",   "limit": 5}, "mix/candles gran=str 1m"),
    ("/api/mix/v1/market/history-candles",  {"granularity": "1min", "limit": 5}, "mix/history-candles gran=str 1min"),
    ("/api/mix/v1/market/history-candles",  {"granularity": 60,     "limit": 5}, "mix/history-candles gran=int 60"),
    ("/api/mix/v1/market/history-candles",  {"granularity": "1m",   "limit": 5}, "mix/history-candles gran=str 1m"),
    # avec productType explicit (certaines routes le demandent sur mix)
    ("/api/mix/v1/market/candles",          {"granularity": "1min", "limit": 5, "productType": "umcbl"}, "mix/candles + productType, 1min"),
    ("/api/mix/v1/market/candles",          {"granularity": 60,     "limit": 5, "productType": "umcbl"}, "mix/candles + productType, 60"),
    ("/api/mix/v1/market/history-candles",  {"granularity": "1min", "limit": 5, "productType": "umcbl"}, "mix/history + productType, 1min"),
    ("/api/mix/v1/market/history-candles",  {"granularity": 60,     "limit": 5, "productType": "umcbl"}, "mix/history + productType, 60"),
]

def norm_symbol(sym: str, market: str) -> str:
    s = sym.upper().replace("-", "")
    suf = "_UMCBL" if market == "umcbl" else "_SPBL"
    if not s.endswith(suf):
        s = s + suf
    return s

def call(path, params):
    url = BASE + path
    try:
        r = requests.get(url, params=params, timeout=15)
        text = r.text
        ok_http = r.ok
        j = {}
        try:
            j = r.json()
        except Exception:
            pass
        code = str(j.get("code", ""))
        ok_api = code in ("0", "00000", "")
        data = j.get("data")
        return ok_http, ok_api, r.status_code, code, (data[:1] if isinstance(data, list) else data), text
    except Exception as e:
        return False, False, -1, "EXC", None, repr(e)

def main():
    results = []
    for sym in SYMBOLS:
        ns = norm_symbol(sym, MARKET)
        for path, params, note in VARIANTS:
            p = dict(params)
            p["symbol"] = ns
            ok_http, ok_api, status, code, sample, raw = call(path, p)
            results.append((note, ns, path, p, ok_http, ok_api, status, code, sample))
            tag = "✅" if (ok_http and ok_api and sample) else "❌"
            print(f"{tag} {note:35s}  sym={ns:15s}  {path}  status={status} code={code} sample={sample}")
            # Si on trouve une variante qui marche, on s'arrête (tu peux commenter si tu veux tout voir).
            if ok_http and ok_api and sample:
                print("\n>>> WINNER")
                print(json.dumps({
                    "symbol": ns,
                    "path": path,
                    "params": p
                }, indent=2))
                return
            time.sleep(0.2)
    print("\nAucune variante valide trouvée (vérifie le symbole / la route).")

if __name__ == "__main__":
    main()
