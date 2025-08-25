#!/usr/bin/env python3
# jobs/refresh_pairs.py
from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from engine.config.loader import load_config

# Exchange: CCXT si dispo sinon REST Bitget
from engine.exchange.bitget_rest import BitgetFuturesClient as BitgetRESTClient
try:
    from engine.exchange.bitget_ccxt import CCXTFuturesClient as BitgetCCXTClient  # type: ignore
    _HAS_CCXT = True
except Exception:
    _HAS_CCXT = False


# ---------- utils FS ----------

def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def _ohlcv_path(data_dir: str, symbol: str, tf: str) -> Path:
    return _ensure_dir(Path(data_dir) / "ohlcv" / symbol) / f"{tf}.csv"

def _write_csv_ohlcv(path: Path, rows: Iterable[List[float]]) -> None:
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for r in rows:
            try:
                ts = int(r[0])
                o, h, l, c = float(r[1]), float(r[2]), float(r[3]), float(r[4])
                v = float(r[5]) if len(r) > 5 else 0.0
                w.writerow([ts, o, h, l, c, v])
            except Exception:
                continue


# ---------- exchange helpers ----------

def _fetch_ohlcv_any(ex, symbol: str, timeframe: str, limit: int = 1000) -> List[List[float]]:
    # 1) CCXT sync si dispo
    fetch = getattr(ex, "fetch_ohlcv", None)
    if callable(fetch):
        try:
            data = fetch(symbol, timeframe, limit=limit)
            return list(data or [])
        except Exception:
            pass
    # 2) REST Bitget (wrapper)
    get_klines = getattr(ex, "get_klines", None)
    if callable(get_klines):
        try:
            resp = get_klines(symbol, interval=timeframe, limit=int(limit))
            rows = resp.get("data") or []
            out: List[List[float]] = []
            for r in rows:
                try:
                    out.append([
                        int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                        float(r[4]), float(r[5]) if len(r) > 5 else 0.0
                    ])
                except Exception:
                    continue
            out.sort(key=lambda x: x[0])
            return out
        except Exception:
            pass
    return []

def _list_usdt_perps_any(ex) -> List[str]:
    # CCXT: via load_markets()
    load_markets = getattr(ex, "load_markets", None)
    if callable(load_markets):
        try:
            markets = load_markets() or {}
            syms: List[str] = []
            for m in markets.values():
                sym = str(m.get("symbol") or "")
                typ = str(m.get("type") or "")
                if "USDT" in sym and typ in {"swap", "future", "perpetual"}:
                    syms.append(sym.replace("_", "").upper())
            if syms:
                return sorted(set(syms))
        except Exception:
            pass
    # REST wrapper: méthode custom facultative
    list_symbols = getattr(ex, "list_symbols", None)
    if callable(list_symbols):
        try:
            items = list_symbols() or []
            out = [str(s).replace("_", "").upper() for s in items if "USDT" in str(s).upper()]
            if out:
                return sorted(set(out))
        except Exception:
            pass
    # Fallback statique
    return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
            "ADAUSDT","DOGEUSDT","LTCUSDT","MATICUSDT","LINKUSDT"]

def _build_exchange():
    if _HAS_CCXT:
        try:
            return BitgetCCXTClient(paper=True)  # si ton wrapper supporte paper
        except Exception:
            pass
    return BitgetRESTClient(base="https://api.bitget.com")


# ---------- scoring ----------

@dataclass
class PairScore:
    symbol: str
    vol_usd_24h: float
    atr_pct_24h: float
    score: float

def _atr_pct_estimate(ohlcv: List[List[float]]) -> float:
    if len(ohlcv) < 50:
        return 0.0
    rng = [(r[2] - r[3]) for r in ohlcv[-200:]]
    atr = sum(abs(x) for x in rng) / max(1, len(rng))
    close = float(ohlcv[-1][4])
    return (atr / close) if close > 0 else 0.0

def _score_pairs(ex, symbols: List[str], timeframe: str, limit: int) -> List[PairScore]:
    out: List[PairScore] = []
    for s in symbols:
        ohlcv = _fetch_ohlcv_any(ex, s, timeframe, limit=min(1000, limit))
        if not ohlcv:
            continue
        vol_usd = 0.0
        for r in ohlcv[-500:]:
            try:
                vol_usd += float(r[4]) * float(r[5])
            except Exception:
                pass
        atr_pct = _atr_pct_estimate(ohlcv)
        score = vol_usd * (1.0 + 10.0 * atr_pct)
        out.append(PairScore(symbol=s, vol_usd_24h=vol_usd, atr_pct_24h=atr_pct, score=score))
        time.sleep(0.03)  # anti rate‑limit léger
    out.sort(key=lambda x: x.score, reverse=True)
    return out


# ---------- watchlist IO ----------

def _save_watchlist(path: Path, scores: List[PairScore], top: int) -> None:
    selected = scores[:top] if top > 0 else scores
    doc = {
        "generated_at": int(time.time() * 1000),
        "top": [
            {
                "symbol": s.symbol,
                "vol_usd_24h": s.vol_usd_24h,
                "atr_pct_24h": s.atr_pct_24h,
                "score": s.score,
            }
            for s in selected
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


# ---------- main ----------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rafraîchit watchlist + backfill OHLCV")
    ap.add_argument("--timeframe", type=str, default="5m", help="TF utilisé pour scorer la watchlist")
    ap.add_argument("--top", type=int, default=10, help="Garder les N meilleures paires (0=toutes)")
    ap.add_argument("--backfill-tfs", type=str, default="1m,5m,15m", help="TFs à backfiller")
    ap.add_argument("--limit", type=int, default=1500, help="Nombre de bougies à récupérer par TF")
    ns = ap.parse_args(argv)

    cfg = load_config()
    rt = cfg.get("runtime", {})
    data_dir = str(rt.get("data_dir") or "/notebooks/scalp_data/data")
    reports_dir = str(rt.get("reports_dir") or "/notebooks/scalp_data/reports")

    ex = _build_exchange()

    # 1) universe
    symbols = _list_usdt_perps_any(ex)
    if not symbols:
        print("[refresh] aucun symbole listé — abandon.")
        return 2

    # 2) scoring
    scores = _score_pairs(ex, symbols, ns.timeframe, ns.limit)
    if not scores:
        print("[refresh] aucun score — abandon.")
        return 3

    # 3) write watchlist
    _save_watchlist(Path(reports_dir) / "watchlist.yml", scores, ns.top)
    selected = [s.symbol for s in (scores[:ns.top] if ns.top > 0 else scores)]
    print(f"[refresh] watchlist top={ns.top}: {', '.join(selected)}")

    # 4) backfill
    tfs = [t.strip() for t in ns.backfill_tfs.split(",") if t.strip()]
    for tf in tfs:
        for sym in selected:
            ohlcv = _fetch_ohlcv_any(ex, sym, tf, limit=ns.limit)
            if not ohlcv:
                print(f"[refresh] pas de données pour {sym}:{tf}")
                continue
            _write_csv_ohlcv(_ohlcv_path(data_dir, sym, tf), ohlcv)
            time.sleep(0.02)  # anti rate‑limit

    print("[refresh] terminé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())