#!/usr/bin/env python3
# jobs/maintainer.py

# --- bootstrap chemin + sitecustomize ---
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    import sitecustomize  # charge .env si présent
except Exception:
    pass
# --- fin bootstrap ---

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import sys as _sys
import time
from typing import List, Tuple

from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.config.strategies import load_strategies

# ---------- logging dédié maintainer ----------
def _setup_logging() -> logging.Logger:
    cfg = load_config()
    rt = cfg.get("runtime", {})
    logs_dir = Path(rt.get("logs_dir") or "/notebooks/scalp_data/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "maintainer.log"

    logger = logging.getLogger("maintainer")
    if logger.handlers:
        return logger  # déjà configuré

    logger.setLevel(logging.INFO)

    # fichier rotatif
    fh = RotatingFileHandler(str(log_path), maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # console (lisible dans la sortie notebook/terminal)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[maintainer] %(message)s"))
    logger.addHandler(ch)

    logger.info("Logger prêt • fichier=%s", log_path)
    return logger

log = _setup_logging()

def sh(cmd: List[str], cwd: Path | None = None) -> int:
    log.info("+ %s", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd or ROOT)).returncode

def _symbols_top(top: int | None) -> List[str]:
    wl = load_watchlist()
    syms = [(d.get("symbol") or "").replace("_","").upper() for d in (wl.get("top") or []) if d.get("symbol")]
    return syms if not top else syms[:top]

def _expired_pairs(tfs: List[str]) -> List[Tuple[str,str]]:
    all_ = load_strategies()
    need: List[Tuple[str,str]] = []
    seen = {(k.split(":")[0], k.split(":")[1]) for k,_ in all_.items()}
    for k,v in all_.items():
        sym, tf = k.split(":")
        if v.get("expired"):
            need.append((sym, tf))
    wl_syms = {s for s in _symbols_top(None)}
    for s in wl_syms:
        for tf in tfs:
            if (s, tf) not in seen:
                need.append((s, tf))
    out, seen2 = [], set()
    for t in need:
        if t not in seen2:
            out.append(t); seen2.add(t)
    return out

def refresh_watchlist(top: int, score_tf: str, backfill_tfs: List[str], limit: int) -> None:
    rc = sh([_sys.executable, "jobs/refresh_pairs.py",
             "--timeframe", score_tf, "--top", str(top),
             "--backfill-tfs", ",".join(backfill_tfs), "--limit", str(limit)])
    if rc != 0:
        log.warning("refresh_pairs.py RC=%s (continue)", rc)

def backfill_symbol_tf(symbol: str, tf: str, limit: int) -> None:
    rc = sh([_sys.executable, "jobs/refresh_pairs.py",
             "--timeframe", tf, "--top", "0",
             "--backfill-tfs", tf, "--limit", str(limit)])
    if rc != 0:
        log.warning("backfill %s:%s RC=%s", symbol, tf, rc)

def backtest_and_promote() -> None:
    rc = sh([_sys.executable, "jobs/backtest.py", "--from-watchlist", "--tfs", "1m,5m,15m,1h"])
    if rc != 0: log.warning("backtest RC=%s", rc)
    rc = sh([_sys.executable, "jobs/promote.py", "--draft", "/notebooks/scalp_data/reports/strategies.yml.next"])
    if rc != 0: log.warning("promote RC=%s", rc)

def run_once(top: int, score_tf: str, tfs: List[str], limit: int, sleep_between_secs: int = 2) -> None:
    log.info("=== RUN ONCE === top=%s score_tf=%s tfs=%s limit=%s", top, score_tf, tfs, limit)
    refresh_watchlist(top=top, score_tf=score_tf, backfill_tfs=tfs, limit=limit)

    syms = _symbols_top(top)
    if not syms:
        log.warning("watchlist vide.")
        return

    todo = _expired_pairs(tfs)
    todo = [(s,tf) for (s,tf) in todo if s in syms]
    log.info("à remettre à jour: %d éléments", len(todo))

    touched = False
    for s in syms:
        for tf in tfs:
            if (s, tf) in todo:
                log.info("backfill ciblé %s:%s", s, tf)
                backfill_symbol_tf(s, tf, limit=limit)
                touched = True
                time.sleep(max(0, sleep_between_secs))

    if touched:
        log.info("backtest → promote…")
        backtest_and_promote()
    else:
        log.info("rien d'expiré — skip backtest.")

def _cfg_vals():
    cfg = load_config()
    wl = cfg.get("watchlist", {})
    mt = cfg.get("maintainer", {})
    return {
        "top": int(wl.get("top", 10)),
        "score_tf": str(wl.get("score_tf", "5m")),
        "tfs": [str(x) for x in (wl.get("backfill_tfs") or ["1m","5m","15m"])],
        "limit": int(wl.get("backfill_limit", 1500)),
        "interval": int(mt.get("interval_secs", 43200)),
    }

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--score-tf", type=str, default=None)
    ap.add_argument("--tfs", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--interval", type=int, default=None)
    ap.add_argument("--once", action="store_true")
    ns = ap.parse_args(argv)

    base = _cfg_vals()
    top = ns.top if ns.top is not None else base["top"]
    score_tf = ns.score_tf if ns.score_tf is not None else base["score_tf"]
    tfs = [t.strip() for t in (ns.tfs or ",".join(base["tfs"])).split(",") if t.strip()]
    limit = ns.limit if ns.limit is not None else base["limit"]
    interval = ns.interval if ns.interval is not None else base["interval"]

    if ns.once:
        run_once(top, score_tf, tfs, limit)
        return 0

    while True:
        try:
            run_once(top, score_tf, tfs, limit)
        except Exception as e:
            log.exception("erreur: %s", e)
        time.sleep(max(300, interval))

if __name__ == "__main__":
    raise SystemExit(main())