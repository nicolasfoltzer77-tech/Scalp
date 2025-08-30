# jobs/build_watchlist.py
from __future__ import annotations
import os, time, math, json, argparse
from pathlib import Path
from typing import List, Dict, Any

import yaml
import ccxt

def to_base(sym_ex: str) -> str:
    # "BTC/USDT:USDT" -> "BTC"
    return sym_ex.split("/")[0]

def from_bitget_symbol(s: str) -> str:
    # "BTC/USDT:USDT" -> "BTCUSDT"
    return f"{to_base(s)}USDT"

def load_cfg() -> Dict[str, Any]:
    return yaml.safe_load(Path("/opt/scalp/engine/config/config.yaml").read_text(encoding="utf-8"))["runtime"]

def stddev(xs: List[float]) -> float:
    n = len(xs); 
    if n < 2: return 0.0
    m = sum(xs)/n
    v = sum((x-m)*(x-m) for x in xs)/(n-1)
    return math.sqrt(v)

def recent_volatility_1m(ex: ccxt.Exchange, sym_ex: str, minutes: int) -> float:
    limit = min(max(minutes, 20), 1000)
    try:
        ohlcv = ex.fetch_ohlcv(sym_ex, timeframe="1m", limit=limit)
    except Exception:
        return 0.0
    closes = [c[4] for c in ohlcv]
    rets = [(closes[i]-closes[i-1])/closes[i-1] for i in range(1,len(closes)) if closes[i-1]>0]
    return stddev(rets)

def build_watchlist(cfg: Dict[str, Any], market: str = "umcbl") -> Dict[str, Any]:
    wl_cfg = cfg.get("watchlist", {})
    max_symbols = int(wl_cfg.get("max_symbols", 12))
    min_vol_usdt = float(wl_cfg.get("min_volume_usdt", 1_000_000))
    vol_window = int(wl_cfg.get("vol_window_minutes", 240))
    w_vol = float(wl_cfg.get("weight_vol", 0.4))
    w_amt = float(wl_cfg.get("weight_volume", 0.6))
    include_manual = bool(wl_cfg.get("include_manual", True))
    manual = [s for s in cfg.get("manual_symbols", []) if s]

    ex = ccxt.bitget({"enableRateLimit": True})
    ex.load_markets()
    # USDT perp only (swap & linear & quote=USDT)
    symbols_ex = [m["symbol"] for m in ex.markets.values()
                  if m.get("swap") and m.get("linear") and m.get("quote")=="USDT"]

    # Tick 24h
    try:
        tickers = ex.fetch_tickers(symbols_ex)
    except Exception:
        tickers = {}
        for s in symbols_ex:
            try:
                tickers[s] = ex.fetch_ticker(s); time.sleep(0.05)
            except Exception:
                pass

    candidates = []
    for s in symbols_ex:
        t = tickers.get(s, {}) or {}
        last = t.get("last") or t.get("info", {}).get("lastPr") or 0.0
        base_vol = t.get("baseVolume") or 0.0
        vol_usdt = (base_vol or 0.0) * (last or 0.0)
        if vol_usdt < min_vol_usdt:
            continue
        vol_ret = recent_volatility_1m(ex, s, minutes=vol_window)
        candidates.append({"sym_ex": s, "sym": from_bitget_symbol(s),
                           "base": to_base(s), "last": last,
                           "vol_usdt": vol_usdt, "vol_ret": vol_ret})
        time.sleep(0.02)

    if not candidates:
        return {"symbols": manual[:max_symbols], "items": [], "ts": int(time.time())}

    # Dé-dup par base: garde la ligne au plus gros vol_usdt
    by_base: Dict[str, Dict[str,Any]] = {}
    for r in candidates:
        b = r["base"]
        if b not in by_base or r["vol_usdt"] > by_base[b]["vol_usdt"]:
            by_base[b] = r
    rows = list(by_base.values())

    # Normalisation + score
    min_amt, max_amt = min(r["vol_usdt"] for r in rows), max(r["vol_usdt"] for r in rows)
    min_ret, max_ret = min(r["vol_ret"] for r in rows), max(r["vol_ret"] for r in rows)
    def norm(x,a,b): return 0.0 if b<=a else (x-a)/(b-a)
    for r in rows:
        s_amt = norm(r["vol_usdt"], min_amt, max_amt)
        s_vol = norm(r["vol_ret"],  min_ret, max_ret)
        r["score"] = w_amt*s_amt + w_vol*s_vol
    rows.sort(key=lambda x: x["score"], reverse=True)

    ranked = [r["sym"] for r in rows]
    if include_manual:
        for m in manual:
            if m not in ranked:
                ranked.insert(0, m)

    symbols: List[str] = []
    for s in ranked:
        if s not in symbols:
            symbols.append(s)
        if len(symbols) >= max_symbols:
            break

    return {"symbols": symbols, "items": rows, "ts": int(time.time())}

def main():
    cfg = load_cfg()
    wl = build_watchlist(cfg, os.environ.get("LIVE_MARKET","umcbl"))
    out_json = Path(cfg["reports_dir"]) / "watchlist.json"
    out_yaml = Path(cfg["reports_dir"]) / "watchlist.yml"
    out_json.write_text(json.dumps(wl, indent=2), encoding="utf-8")
    out_yaml.write_text(yaml.safe_dump(wl, sort_keys=False), encoding="utf-8")
    print(f"[watchlist] saved -> {out_json} ({len(wl['symbols'])} syms)")

if __name__ == "__main__":
    main()
