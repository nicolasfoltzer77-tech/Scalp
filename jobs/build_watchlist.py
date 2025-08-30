# jobs/build_watchlist.py
from __future__ import annotations
import os, time, math, json, argparse
from pathlib import Path
from typing import List, Dict, Any

import yaml
import ccxt

TF_MS = {"1m": 60_000}

def to_bitget_perp(sym: str) -> str:
    # "BTCUSDT" -> "BTC/USDT:USDT"
    return f"{sym[:-4]}/USDT:USDT" if sym.endswith("USDT") else sym

def from_bitget_symbol(s: str) -> str:
    # "BTC/USDT:USDT" -> "BTCUSDT"
    if s.endswith(":USDT") and "/USDT" in s:
        base = s.split("/")[0]
        return f"{base}USDT"
    return s.replace("/","").replace(":USDT","USDT")

def load_cfg() -> Dict[str, Any]:
    cfg = yaml.safe_load(Path("/opt/scalp/engine/config/config.yaml").read_text(encoding="utf-8"))["runtime"]
    return cfg

def stddev(xs: List[float]) -> float:
    n = len(xs)
    if n < 2: return 0.0
    m = sum(xs)/n
    v = sum((x-m)*(x-m) for x in xs)/(n-1)
    return math.sqrt(v)

def recent_volatility_1m(ex: ccxt.Exchange, sym_ex: str, minutes: int) -> float:
    limit = min(max(minutes, 20), 1000)  # cap
    try:
        ohlcv = ex.fetch_ohlcv(sym_ex, timeframe="1m", limit=limit)
    except Exception:
        return 0.0
    closes = [c[4] for c in ohlcv]
    rets = []
    for i in range(1, len(closes)):
        if closes[i-1] > 0:
            rets.append((closes[i]-closes[i-1]) / closes[i-1])
    return stddev(rets)

def build_watchlist(cfg: Dict[str, Any], market: str = "umcbl") -> Dict[str, Any]:
    wl_cfg = cfg.get("watchlist", {})
    max_symbols: int = int(wl_cfg.get("max_symbols", 12))
    min_vol_usdt: float = float(wl_cfg.get("min_volume_usdt", 1_000_000))
    vol_window: int = int(wl_cfg.get("vol_window_minutes", 240))
    w_vol: float = float(wl_cfg.get("weight_vol", 0.4))
    w_amt: float = float(wl_cfg.get("weight_volume", 0.6))
    include_manual: bool = bool(wl_cfg.get("include_manual", True))
    manual = [s for s in cfg.get("manual_symbols", []) if s]

    ex = ccxt.bitget({"enableRateLimit": True})
    ex.load_markets()
    # on prend tous les swaps USDT linéaires (perp)
    symbols_ex = []
    for m in ex.markets.values():
        try:
            if not (m.get("swap") and m.get("linear")): 
                continue
            if m.get("quote") != "USDT": 
                continue
            symbols_ex.append(m["symbol"])  # ex: "BTC/USDT:USDT"
        except Exception:
            continue

    # Tick data 24h pour volume/last
    try:
        tickers = ex.fetch_tickers(symbols_ex)
    except Exception:
        # fallback: ticker à l'unité (plus lent)
        tickers = {}
        for s in symbols_ex:
            try:
                tickers[s] = ex.fetch_ticker(s)
                time.sleep(0.05)
            except Exception:
                pass

    rows = []
    # Pré-calculs min/max pour normalisation
    vols_usdt = []
    vols_ret = []
    for s in symbols_ex:
        t = tickers.get(s, {}) or {}
        last = t.get("last") or t.get("info", {}).get("lastPr") or 0.0
        base_vol = t.get("baseVolume") or 0.0
        vol_usdt = (base_vol or 0.0) * (last or 0.0)
        if vol_usdt <= 0:
            continue
        if vol_usdt < min_vol_usdt:
            continue
        # volatilité récente (1m * vol_window)
        vol_ret = recent_volatility_1m(ex, s, minutes=vol_window)
        rows.append({"sym_ex": s, "sym": from_bitget_symbol(s), "last": last, "vol_usdt": vol_usdt, "vol_ret": vol_ret})
        vols_usdt.append(vol_usdt)
        vols_ret.append(vol_ret)
        time.sleep(0.02)

    if not rows:
        # fallback minimal : on renvoie la liste manuelle (au moins)
        return {"symbols": manual[:max_symbols], "items": [], "ts": int(time.time())}

    min_amt, max_amt = min(vols_usdt), max(vols_usdt)
    min_ret, max_ret = min(vols_ret or [0.0]), max(vols_ret or [1.0])

    def norm(x, a, b):
        if b <= a: return 0.0
        return (x - a) / (b - a)

    for r in rows:
        s_amt = norm(r["vol_usdt"], min_amt, max_amt)
        s_vol = norm(r["vol_ret"], min_ret, max_ret)
        r["score"] = w_amt * s_amt + w_vol * s_vol

    rows.sort(key=lambda x: x["score"], reverse=True)
    # applique manuel si demandé
    ranked = [r["sym"] for r in rows]
    if include_manual:
        for m in manual:
            if m not in ranked:
                ranked.insert(0, m)

    symbols = []
    for s in ranked:
        if s not in symbols:
            symbols.append(s)
        if len(symbols) >= max_symbols:
            break

    return {"symbols": symbols, "items": rows, "ts": int(time.time())}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()

    cfg = load_cfg()
    market = os.environ.get("LIVE_MARKET", "umcbl")
    wl = build_watchlist(cfg, market)
    if args.max:
        wl["symbols"] = wl["symbols"][:args.max]

    out_json = Path(cfg["reports_dir"]) / "watchlist.json"
    out_yaml = Path(cfg["reports_dir"]) / "watchlist.yml"
    out_json.write_text(json.dumps(wl, indent=2), encoding="utf-8")
    out_yaml.write_text(yaml.safe_dump(wl, sort_keys=False), encoding="utf-8")
    print(f"[watchlist] saved -> {out_json} ({len(wl['symbols'])} syms)")

if __name__ == "__main__":
    main()
