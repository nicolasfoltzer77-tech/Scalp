# engine/backtest/runner.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List

from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.signals.factory import load_strategies_cfg          # <- FIX d'import
from engine.backtest.loader_csv import load_csv_ohlcv           # lecteur OHLCV CSV

# -------------------------------------------------------------

@dataclass
class DraftStrategy:
    name: str = "ema_cross_atr"
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    trail_atr_mult: float = 2.0
    risk_pct_equity: float = 0.5
    created_at: int = 0        # ms epoch
    ttl_bars: int = 240        # durée de vie par défaut (ex: 240 barres)
    expired: bool = False

def _now_ms() -> int:
    return int(time.time() * 1000)

def _pairs_from_watchlist(top: int | None = None) -> List[str]:
    wl = load_watchlist()
    items = wl.get("top") or []
    syms = [(d.get("symbol") or "").replace("_", "").upper() for d in items if d.get("symbol")]
    return syms[:top] if top and top > 0 else syms

def _load_universe(from_watchlist: bool, top: int | None) -> List[str]:
    if from_watchlist:
        syms = _pairs_from_watchlist(top)
        if syms:
            return syms
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def _baseline_params(tf: str) -> DraftStrategy:
    if tf == "1m":
        return DraftStrategy(ema_fast=9,  ema_slow=21, atr_period=14, trail_atr_mult=2.2, risk_pct_equity=0.4)
    if tf == "5m":
        return DraftStrategy(ema_fast=12, ema_slow=26, atr_period=14, trail_atr_mult=2.0, risk_pct_equity=0.5)
    if tf == "15m":
        return DraftStrategy(ema_fast=20, ema_slow=50, atr_period=14, trail_atr_mult=1.8, risk_pct_equity=0.6)
    if tf == "1h":
        return DraftStrategy(ema_fast=34, ema_slow=89, atr_period=14, trail_atr_mult=1.6, risk_pct_equity=0.7)
    return DraftStrategy()

def _has_enough_data(data_dir: str, symbol: str, tf: str, min_rows: int = 200) -> bool:
    try:
        rows = load_csv_ohlcv(data_dir, symbol, tf, max_rows=min_rows)
        return len(rows) >= min_rows
    except Exception:
        return False

def run_backtests(*, from_watchlist: bool, tfs: Iterable[str]) -> Path:
    """
    Produit un draft minimal 'strategies.yml.next' sous reports/.
    On génère des stratégies de base (baseline) pour chaque (symbol, tf)
    ayant assez d'historique. Le vrai scoring/perf pourra être ajouté plus tard.
    """
    cfg = load_config()
    rt = cfg.get("runtime", {})
    data_dir = str(rt.get("data_dir") or "/notebooks/scalp_data/data")
    reports_dir = str(rt.get("reports_dir") or "/notebooks/scalp_data/reports")
    Path(reports_dir).mkdir(parents=True, exist_ok=True)

    top = int(cfg.get("watchlist", {}).get("top", 10))
    symbols = _load_universe(from_watchlist=from_watchlist, top=top)
    tfs_list = [str(tf) for tf in tfs]
    created = _now_ms()

    draft: Dict[str, Dict] = {"strategies": {}}

    # overrides utilisateur (facultatifs)
    try:
        user_overrides = load_strategies_cfg() or {}
    except Exception:
        user_overrides = {}

    defaults = user_overrides.get("defaults") or {}

    for s in symbols:
        for tf in tfs_list:
            if not _has_enough_data(data_dir, s, tf, min_rows=200):
                continue
            params = _baseline_params(tf)
            params.created_at = created
            key = f"{s}:{tf}"
            specific = user_overrides.get(key) or {}
            draft["strategies"][key] = {**asdict(params), **defaults, **specific}

    out_path = Path(reports_dir) / "strategies.yml.next"
    out_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    return out_path