#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Backtest modulaire :
- Lit watchlist + CSV OHLCV
- Calcule métriques simples (PF, MDD, WR, Sharpe) via une stratégie placeholder (ex: EMA/ATR)
- Écrit summary.json (agrégé) et strategies.yml.next (candidats)
- I/O atomiques + backups, logs JSON, retry réseau stub

NB: Stratégie volontairement simplifiée ici pour la stabilité; branche ton moteur réel dans `run_strategy`.
"""

from __future__ import annotations
import os, sys, json, math, time, yaml
from dataclasses import dataclass
from typing import List, Dict, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(PROJECT_ROOT)

from engine.utils.io_safe import atomic_write_json, atomic_write_text, backup_last_good
from engine.utils.logging_setup import setup_logger
from engine.utils.retry import retry

# ----------------- Config paths
CONFIG_YAML  = os.path.join(PROJECT_ROOT, "engine", "config", "config.yaml")
STRATS_NEXT  = lambda reports_dir: os.path.join(reports_dir, "strategies.yml.next")
SUMMARY_JSON = lambda reports_dir: os.path.join(reports_dir, "summary.json")
WATCHLIST_YML= lambda reports_dir: os.path.join(reports_dir, "watchlist.yml")

# ----------------- Helpers config
def load_yaml(path, missing_ok=False):
    if missing_ok and not os.path.isfile(path): return {}
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f) or {}

def save_yaml(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    atomic_write_text(yaml.safe_dump(obj, sort_keys=True, allow_unicode=True, default_flow_style=False), path)

def tf_minutes(tf: str) -> int:
    if tf.endswith("m"): return int(tf[:-1])
    if tf.endswith("h"): return int(tf[:-1]) * 60
    if tf.endswith("d"): return int(tf[:-1]) * 1440
    raise ValueError(f"TF non supporté: {tf}")

# ----------------- Data loading (CSV)
def ohlcv_path(data_dir: str, pair: str, tf: str) -> str:
    return os.path.join(data_dir, "ohlcv", pair, f"{tf}.csv")

def load_csv_fast(path: str):
    import pandas as pd
    usecols = ["timestamp","open","high","low","close","volume"]
    if not os.path.isfile(path): return None
    try:
        df = pd.read_csv(path, usecols=usecols, dtype={
            "timestamp":"int64","open":"float64","high":"float64","low":"float64","close":"float64","volume":"float64"
        }, engine="c")
        df = df.sort_values("timestamp").dropna()
        return df
    except Exception:
        return None

# ----------------- Strategy placeholder (à brancher)
@dataclass
class Metrics:
    pf: float
    mdd: float
    trades: int
    wr: float
    sharpe: float

def run_strategy(df) -> Metrics:
    """
    Placeholder très simple :
    - Trades fictifs à chaque croisement EMA(12) / EMA(34)
    - SL/TP fictifs basés sur ATR(14) (approx)
    Objectif : produire des métriques stables pour la pipeline.
    """
    import numpy as np
    import pandas as pd

    if df is None or len(df) < 200:
        return Metrics(1.0, 0.5, 0, 0.0, 0.0)

    price = df["close"].values.astype("float64")
    vol = df["volume"].values.astype("float64")

    # EMA rapides/lentes
    def ema(a, n):
        alpha = 2/(n+1)
        out = np.empty_like(a); out[:] = np.nan
        prev = a[0]
        for i,x in enumerate(a):
            prev = alpha*x + (1-alpha)*prev
            out[i] = prev
        # lissage initial
        for i in range(1, n):
            out[i] = np.nan
        return out

    ema12 = ema(price, 12)
    ema34 = ema(price, 34)

    # signaux: croisement
    longs = (ema12[1:] >= ema34[1:]) & (ema12[:-1] < ema34[:-1])
    shorts= (ema12[1:] <= ema34[1:]) & (ema12[:-1] > ema34[:-1])

    # PnL simplifié: diff sur N barres
    pnl = []
    trades = 0
    look = 10
    for i, sig in enumerate(longs, start=1):
        if sig and i+look < len(price):
            r = (price[i+look] - price[i]) / price[i]
            pnl.append(r); trades += 1
    for i, sig in enumerate(shorts, start=1):
        if sig and i+look < len(price):
            r = (price[i] - price[i+look]) / price[i]
            pnl.append(r); trades += 1

    if trades == 0:
        return Metrics(1.0, 0.5, 0, 0.0, 0.0)

    pnl = np.array(pnl)
    wins = (pnl > 0).sum()
    wr = wins / trades
    gross_gain = pnl[pnl>0].sum()
    gross_loss = -pnl[pnl<0].sum()
    pf = (gross_gain / gross_loss) if gross_loss > 1e-12 else 2.0

    # equity & MDD
    eq = (1.0 + pnl).cumprod()
    peak = np.maximum.accumulate(eq)
    dd = 1.0 - eq/peak
    mdd = float(np.nanmax(dd)) if len(dd) else 0.0

    # Sharpe simplifié (pnl bar-return, pas annualisé ici)
    if pnl.std() > 1e-12:
        sharpe = float(pnl.mean() / pnl.std())
    else:
        sharpe = 0.0

    return Metrics(float(pf), float(mdd), int(trades), float(wr), float(sharpe))

# ----------------- Row builder
def make_row(pair: str, tf: str, met: Metrics) -> Dict:
    return {
        "pair": pair,
        "tf": tf,
        "pf": round(met.pf, 6),
        "mdd": round(met.mdd, 6),
        "trades": int(met.trades),
        "wr": round(met.wr, 6),
        "sharpe": round(met.sharpe, 6),
    }

def make_candidate(pair: str, tf: str, met: Metrics, now_ts: int) -> Tuple[str, Dict]:
    key = f"{pair}:{tf}"
    cand = {
        "name": "ema_atr_v1",
        "ema_fast": 12,
        "ema_slow": 34,
        "atr_period": 14,
        "trail_atr_mult": 2.0,
        "risk_pct_equity": 0.5,
        "created_at": now_ts,
        "expires_at": None,
        "expired": False,
        "metrics": {
            "pf": round(met.pf,6),
            "mdd": round(met.mdd,6),
            "trades": int(met.trades),
            "wr": round(met.wr,6),
            "sharpe": round(met.sharpe,6),
        }
    }
    return key, cand

# ----------------- Watchlist
def load_watchlist(reports_dir: str, topN: int | None = None) -> List[str]:
    wl_path = WATCHLIST_YML(reports_dir)
    wl = load_yaml(wl_path, missing_ok=True)
    pairs = wl.get("pairs") or wl.get("watchlist") or []
    pairs = [p for p in pairs if isinstance(p, str)]
    if topN:
        pairs = pairs[:topN]
    return pairs

# ----------------- Main run per (pair, tf)
def process_pair_tf(data_dir: str, pair: str, tf: str) -> Tuple[Dict, Tuple[str, Dict]]:
    df = load_csv_fast(ohlcv_path(data_dir, pair, tf))
    met = run_strategy(df)
    now_ts = int(time.time())
    row = make_row(pair, tf, met)
    cand = make_candidate(pair, tf, met, now_ts)
    return row, cand

# ----------------- run()
def run():
    cfg = load_yaml(CONFIG_YAML, missing_ok=True)
    rt = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    data_dir = rt.get("data_dir", "/notebooks/scalp_data/data")
    reports_dir = rt.get("reports_dir", "/notebooks/scalp_data/reports")
    tf_list = rt.get("tf_list", ["1m","5m","15m"])
    topN = int(rt.get("topN", 10))

    logs_dir = os.path.join(os.path.dirname(data_dir), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    log = setup_logger("backtest", os.path.join(logs_dir, "backtest.log"))
    log.info({"event":"start","tf_list":tf_list,"topN":topN})

    pairs = load_watchlist(reports_dir, topN=topN)
    if not pairs:
        log.info({"event":"no_watchlist"})
        return

    rows: List[Dict] = []
    cands: Dict[str, Dict] = {}

    tasks = []
    from multiprocessing import cpu_count
    max_workers = min(8, (cpu_count() or 2))
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        for pair in pairs:
            for tf in tf_list:
                tasks.append(ex.submit(process_pair_tf, data_dir, pair, tf))
        for fut in as_completed(tasks):
            try:
                row, cand = fut.result()
                rows.append(row)
                key, val = cand
                cands[key] = val
            except Exception as e:
                log.info({"event":"pair_tf_error","err":str(e)})

    # summary.json
    summary_path = SUMMARY_JSON(reports_dir)
    summary_obj = {"generated_at": int(time.time()), "risk_mode": rt.get("risk_mode","normal"), "rows": rows}

    backup_last_good(summary_path)
    atomic_write_json(summary_obj, summary_path)

    # strategies.yml.next
    next_path = STRATS_NEXT(reports_dir)
    next_obj = {"strategies": cands}

    backup_last_good(next_path)
    save_yaml(next_obj, next_path)

    log.info({"event":"done","rows":len(rows),"cands":len(cands)})

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        # dernier filet
        print(json.dumps({"lvl":"ERROR","msg":str(e)}))
        sys.exit(1)