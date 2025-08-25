#!/usr/bin/env python3
# jobs/maintainer.py
from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.config.strategies import load_strategies

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("maintainer")


# ------------------------ logging ------------------------

def _setup_logging() -> None:
    if log.handlers:
        return
    cfg = load_config()
    rt = cfg.get("runtime", {})
    logs_dir = Path(rt.get("logs_dir") or "/notebooks/scalp_data/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(str(logs_dir / "maintainer.log"),
                             maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[maintainer] %(levelname)s: %(message)s"))
    log.setLevel(logging.INFO)
    fh.setLevel(logging.INFO)
    ch.setLevel(logging.INFO)
    log.addHandler(fh)
    log.addHandler(ch)
    log.info("Logger prêt • fichier=%s", logs_dir / "maintainer.log")


# ------------------------ helpers ------------------------

def run_cmd(args: List[str]) -> tuple[int, str, str]:
    """Lance une commande en capturant stdout/stderr. Retourne (rc, out, err)."""
    log.info("+ %s", " ".join(args))
    p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    if p.stdout:
        log.info("stdout: %s", p.stdout.strip())
    if p.stderr:
        log.warning("stderr: %s", p.stderr.strip())
    return p.returncode, p.stdout, p.stderr


def _symbols_top(top: int | None) -> List[str]:
    wl = load_watchlist()
    syms = [(d.get("symbol") or "").replace("_", "").upper()
            for d in (wl.get("top") or []) if d.get("symbol")]
    return syms if not top else syms[:top]


def _expired_pairs(tfs: List[str]) -> List[Tuple[str, str]]:
    """
    Renvoie les (symbol, tf) absents/expirés d'après strategies.yml,
    et complète avec les tfs manquants pour la watchlist.
    """
    all_ = load_strategies()
    need: List[Tuple[str, str]] = []
    present = {(k.split(":")[0], k.split(":")[1]) for k in all_.keys()}

    # expirées
    for k, v in all_.items():
        s, tf = k.split(":")
        if v.get("expired"):
            need.append((s, tf))

    wl_syms = set(_symbols_top(None))
    for s in wl_syms:
        for tf in tfs:
            if (s, tf) not in present:
                need.append((s, tf))

    out, seen = [], set()
    for item in need:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out


# ------------------------ actions ------------------------

def refresh_watchlist(top: int, score_tf: str, backfill_tfs: List[str], limit: int) -> None:
    rc, _, _ = run_cmd([
        sys.executable, "-m", "jobs.refresh_pairs",
        "--timeframe", score_tf,
        "--top", str(top),
        "--backfill-tfs", ",".join(backfill_tfs),
        "--limit", str(limit),
    ])
    if rc != 0:
        log.warning("refresh_pairs RC=%s (continue)", rc)


def backfill_symbol_tf(symbol: str, tf: str, limit: int) -> bool:
    """Backfill un (symbol, tf). Retourne True si OK."""
    rc, _, _ = run_cmd([
        sys.executable, "-m", "jobs.refresh_pairs",
        "--timeframe", tf,
        "--top", "0",              # n'altère pas le tri topN
        "--backfill-tfs", tf,
        "--limit", str(limit),
    ])
    ok = (rc == 0)
    if ok:
        log.info("backfill OK: %s:%s", symbol, tf)
    else:
        log.warning("backfill FAIL: %s:%s (rc=%s)", symbol, tf, rc)
    return ok


def backtest_and_promote() -> None:
    """Enchaîne backtest -> promotion, puis journalise un résumé."""
    # 1) backtest (depuis watchlist, multi‑TF)
    rc, _, _ = run_cmd([sys.executable, "-m", "jobs.backtest",
                        "--from-watchlist", "--tfs", "1m,5m,15m,1h"])
    if rc != 0:
        log.warning("backtest RC=%s", rc)

    # 2) promote (draft -> strategies.yml)
    draft = "/notebooks/scalp_data/reports/strategies.yml.next"
    rc, _, _ = run_cmd([sys.executable, "-m", "jobs.promote", "--draft", draft])
    if rc != 0:
        log.warning("promote RC=%s", rc)

    # 3) résumé
    _summary_strategies()


def _summary_strategies() -> None:
    """
    Lit strategies.yml et affiche:
      - total stratégies actives
      - par TF
      - nb expirées
    """
    try:
        strat: Dict[str, Dict] = load_strategies()
        total = len(strat)
        by_tf: Dict[str, int] = {}
        expired = 0
        for k, v in strat.items():
            try:
                _, tf = k.split(":")
            except ValueError:
                tf = "?"
            by_tf[tf] = by_tf.get(tf, 0) + 1
            if v.get("expired"):
                expired += 1

        parts = [f"total={total}", f"expirées={expired}"]
        if by_tf:
            tf_str = ", ".join(f"{tf}:{n}" for tf, n in sorted(by_tf.items()))
            parts.append(f"par_tf=({tf_str})")
        log.info("STRATEGIES • " + " • ".join(parts))
    except Exception as e:
        log.warning("summary strategies impossible: %s", e)


# ------------------------ pipeline ------------------------

def run_once(top: int, score_tf: str, tfs: List[str], limit: int,
             sleep_between_secs: float = 0.5) -> None:
    log.info("=== RUN ONCE === top=%s score_tf=%s tfs=%s limit=%s",
             top, score_tf, tfs, limit)

    # 1) refresh + backfill global rapide
    refresh_watchlist(top=top, score_tf=score_tf, backfill_tfs=tfs, limit=limit)

    # 2) lecture watchlist
    syms = _symbols_top(top)
    log.info("watchlist: %s", ", ".join(syms) if syms else "(vide)")
    if not syms:
        log.warning("Watchlist vide — stop.")
        return

    # 3) éléments expirés/manquants
    todo = [(s, tf) for (s, tf) in _expired_pairs(tfs) if s in syms]
    log.info("à remettre à jour: %d éléments", len(todo))

    # 4) backfill séquentiel 1→N et TF croisés
    touched = False
    for s in syms:
        for tf in tfs:
            if (s, tf) in todo:
                t0 = time.time()
                ok = backfill_symbol_tf(s, tf, limit=limit)
                dt = time.time() - t0
                log.info("elapsed %s:%s = %.2fs", s, tf, dt)
                touched = touched or ok
                time.sleep(max(0.0, sleep_between_secs))

    # 5) si on a touché des données expirées → backtest+promote (+ résumé)
    if touched:
        log.info("backtest → promote…")
        backtest_and_promote()
    else:
        log.info("rien d'expiré — skip backtest.")
        _summary_strategies()  # on log quand même l’état courant


# ------------------------ CLI ------------------------

def _cfg_vals():
    cfg = load_config()
    wl = cfg.get("watchlist", {})
    mt = cfg.get("maintainer", {})
    return {
        "top": int(wl.get("top", 10)),
        "score_tf": str(wl.get("score_tf", "5m")),
        "tfs": [str(x) for x in (wl.get("backfill_tfs") or ["1m", "5m", "15m"])],
        "limit": int(wl.get("backfill_limit", 1500)),
        "interval": int(mt.get("interval_secs", 43200)),
    }


def main(argv=None) -> int:
    _setup_logging()

    ap = argparse.ArgumentParser(description="Mainteneur TOP‑N watchlist + backfill + backtest/promotion")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--score-tf", type=str, default=None)
    ap.add_argument("--tfs", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--interval", type=int, default=None, help="intervalle boucle (sec)")
    ap.add_argument("--once", action="store_true", help="exécute une seule passe et sort")
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
        except Exception:
            log.exception("erreur maintainer")
        time.sleep(max(300, interval))


if __name__ == "__main__":
    raise SystemExit(main())