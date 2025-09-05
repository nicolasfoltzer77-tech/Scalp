#!/usr/bin/env python3
from __future__ import annotations
import os, sys, csv, time, json, pathlib
from typing import List, Dict, Any
import ccxt

BASE = "/opt/scalp"
DATA_DIR = f"{BASE}/data/klines"
CONF = f"{BASE}/config/indicators.yml"
PAIRS_TXT = f"{BASE}/pairs.txt"
WATCHLIST_JSON = f"{BASE}/reports/watchlist.json"

# Map TF scalp -> ccxt
TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m"}

def load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:
        raise SystemExit("pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_pairs() -> List[str]:
    # 1) watchlist.json (si présent)
    if os.path.exists(WATCHLIST_JSON):
        try:
            with open(WATCHLIST_JSON, "r", encoding="utf-8") as f:
                wl = json.load(f)
            if isinstance(wl, dict) and "symbols" in wl:
                return [s.upper() for s in wl["symbols"]]
        except Exception:
            pass
    # 2) fallback pairs.txt (1 symbole par ligne)
    if os.path.exists(PAIRS_TXT):
        out = []
        with open(PAIRS_TXT, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"): 
                    continue
                out.append(s.upper())
        if out: return out
    # défaut minimal
    return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

def history_target(tf: str, cfg: Dict[str, Any]) -> int:
    ht = cfg.get("history_target", {})
    return int(ht.get(tf, 1500))

def ensure_dir(p: str) -> None:
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def read_existing(csv_path: str) -> Dict[int, List[float]]:
    """Retourne dict ts -> row (ts,o,h,l,c,v)"""
    out: Dict[int, List[float]] = {}
    if not os.path.exists(csv_path):
        return out
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        for row in r:
            try:
                ts = int(float(row[0]))
                vals = [float(x) for x in row[:6]]
                out[ts] = vals
            except Exception:
                continue
    return out

def write_csv(csv_path: str, rows: List[List[float]]) -> None:
    ensure_dir(os.path.dirname(csv_path))
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)

def fetch_incremental(exchange, symbol: str, tf: str, target_n: int, csv_path: str) -> None:
    """
    Récupère et merge des OHLCV ccxt: [ts, open, high, low, close, volume]
    Garde les 'target_n' dernières bougies.
    """
    existing = read_existing(csv_path)
    since = None
    # S'il y a déjà des données, on repart de la dernière bougie - (target_n * timeframe)
    if existing:
        last_ts = max(existing.keys())
        # On repart 100 bougies avant pour recoller proprement
        # ccxt gère le 'since' en ms:
        since = (last_ts - 100 * tf_millis(tf)) 
    limit = 1000  # ccxt page size

    all_rows = {k: v for k, v in existing.items()}

    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, TF_MAP[tf], since=since, limit=limit)
        if not ohlcv:
            break
        for ts, o, h, l, c, v in ohlcv:
            # ts en ms → gardons ts en secondes pour homogénéité locale
            sec = int(ts // 1000)
            all_rows[sec] = [sec, float(o), float(h), float(l), float(c), float(v)]
        # stop si on n'avance plus
        if since is not None:
            new_last = ohlcv[-1][0]
            if new_last <= (since or 0):
                break
            since = new_last
        else:
            # première page sans since -> stop après une page
            break

    # Final: tri + trunc
    merged = [all_rows[k] for k in sorted(all_rows.keys())]
    if len(merged) > target_n:
        merged = merged[-target_n:]
    write_csv(csv_path, merged)

def tf_millis(tf: str) -> int:
    mult = {"1m": 60_000, "5m": 5*60_000, "15m": 15*60_000}
    return mult[tf]

def main() -> None:
    cfg = load_yaml(CONF)
    pairs = load_pairs()
    tfs = list(TF_MAP.keys())

    # ccxt bitget (public)
    ex = ccxt.bitget({"enableRateLimit": True})

    for s in pairs:
        for tf in tfs:
            try:
                csv_path = os.path.join(DATA_DIR, f"{s}_{tf}.csv")
                fetch_incremental(ex, s, tf, history_target(tf, cfg), csv_path)
                print(f"[OK] {s} {tf} -> {csv_path}")
            except Exception as e:
                print(f"[WARN] {s} {tf}: {e}", file=sys.stderr)
                time.sleep(0.5)

if __name__ == "__main__":
    main()
