#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scalp Bot (standalone scheduler)
- Lit la watchlist JSON
- Charge les stratégies (compatible retour 1 ou 2 valeurs)
- Évalue les signaux via evaluate_for(...) pour chaque (symbol, tf)
- Log format court: "pipe-<SYM>-<TF> | <SYM>-<TF> close=... sig=<...> pnl=0.0"
"""

from __future__ import annotations
import os, json, time, logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- logging ---------------------------------------------------------------
LOG = logging.getLogger("bot")
LOG.setLevel(logging.INFO)
_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)4s | %(message)s", "%Y-%m-%d %H:%M:%S,%f"))
LOG.addHandler(_h)

# --- stratégies & bridge ---------------------------------------------------
from engine.strategies.runner import load_strategies
from engine.signals.strategy_bridge import evaluate_for

# --- util ------------------------------------------------------------------
def env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "")
    return [x.strip() for x in raw.split(",") if x.strip()] or default

def load_watchlist(path="/opt/scalp/reports/watchlist.json") -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        syms = data.get("symbols", [])
        # USDT only + normalisation
        syms = [s.strip().upper().replace("USDTUSDT","USDT") for s in syms if s.upper().endswith("USDT")]
        # unicité par base (BTC -> BTCUSDT)
        seen = set()
        uniq = []
        for s in syms:
            base = s[:-4] if s.endswith("USDT") else s
            if base not in seen:
                seen.add(base)
                uniq.append(f"{base}USDT")
        return uniq
    except Exception as e:
        LOG.warning("watchlist absente/illisible (%s) -> fallback manuel", e)
        # fallback manuel minimal
        return env_list("BOOTSTRAP_SYMBOLS", ["BTCUSDT","ETHUSDT"])

def load_strats_cfg():
    """Supporte load_strategies() -> strategies ou (strategies, cfg)."""
    out = load_strategies()
    if isinstance(out, tuple):
        return out[0], out[1] if len(out) > 1 else {}
    return out, {}

# --- worker ----------------------------------------------------------------
def eval_symbol_tf(symbol: str, tf: str, strategies: list[dict], cfg: dict) -> dict:
    res = evaluate_for(symbol=symbol, tf=tf, strategies=strategies, config=cfg, ohlcv=None, logger=LOG)
    sig = res.get("combined", "HOLD")
    # petite valeur close si dispo dans details
    details = res.get("details", {})
    close = details.get("close") or details.get("ohlcv", [None, None, None, None, None])[-1] if isinstance(details.get("ohlcv"), list) else None
    LOG.info("pipe-%s-%s | %s-%s close=%s sig=%s pnl=0.0", symbol, tf, symbol, tf, close, sig)
    return {"symbol": symbol, "tf": tf, "sig": sig, "details": res}

# --- main loop -------------------------------------------------------------
def main():
    LOG.info("[bot] starting")
    symbols = load_watchlist()
    tfs = env_list("LIVE_TFS", ["1m","5m","15m"])  # ex: LIVE_TFS="1m,5m,15m"
    max_workers = int(os.environ.get("MAX_CONCURRENCY", "6"))
    sleep_s = int(os.environ.get("PIPELINE_INTERVAL_SEC", "5"))

    LOG.info("[bot] bootstrap symbols: %s", symbols)
    LOG.info("[bot] timeframes: %s | max_concurrency=%s | interval=%ss", tfs, max_workers, sleep_s)

    strategies, cfg = load_strats_cfg()

    while True:
        start = time.time()
        jobs = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for s in symbols:
                for tf in tfs:
                    jobs.append(ex.submit(eval_symbol_tf, s, tf, strategies, cfg))

            # Consomme les résultats (et montre une erreur propre si ça pète)
            for f in as_completed(jobs):
                try:
                    _ = f.result()
                except Exception as e:
                    LOG.error("pipeline task error: %s", e, exc_info=True)

        # cadence
        elapsed = time.time() - start
        wait = max(0.0, sleep_s - elapsed)
        time.sleep(wait)

if __name__ == "__main__":
    main()
