# /opt/scalp/engine/watchlist.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, json, pathlib

REPORTS = pathlib.Path("/opt/scalp/reports/watchlist.json")

DEFAULT_BOOT = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]

def _dedup_usdt(symbols: list[str]) -> list[str]:
    out, seen = [], set()
    for s in symbols:
        if not s or not s.endswith("USDT"):  # USDT-only
            continue
        base = s[:-4]
        if base not in seen:
            seen.add(base); out.append(s)
    return out

def _parse_env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw: return default[:]
    return [x.strip().upper() for x in raw.split(",") if x.strip()]

def load_watchlist() -> dict:
    # 1) depuis reports/watchlist.json si dispo
    syms = []
    if REPORTS.exists():
        try:
            obj = json.loads(REPORTS.read_text())
            syms = obj.get("symbols", []) or obj.get("list", []) or []
        except Exception:
            syms = []

    # 2) fallback -> env MANUAL_SYMBOLS / DEFAULT_BOOT
    if not syms:
        syms = _parse_env_list("MANUAL_SYMBOLS", DEFAULT_BOOT)

    syms = _dedup_usdt([s.upper() for s in syms])

    # TFs
    tfs = _parse_env_list("WATCH_TFS", []) or _parse_env_list("LIVE_TF", []) or ["1m","5m","15m"]
    return {"symbols": syms, "tfs": tfs}
