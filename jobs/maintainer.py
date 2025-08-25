#!/usr/bin/env python3
# jobs/maintainer.py
"""
Mainteneur en arrière‑plan :
- refresh watchlist (TOP N)
- backfill data pour TFs demandés
- si lifetime (TTL en barres) dépassée -> backtest + promote
- exécute séquentiellement : symbol 1..N et TFs croisés

Peut être lancé seul (cron) ou depuis bot.py (tâche asyncio).

Exemples:
  python jobs/maintainer.py --top 10 --score-tf 5m --tfs 1m,5m,15m --limit 1500
"""

from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.config.strategies import load_strategies

ROOT = Path(__file__).resolve().parents[1]

def sh(cmd: List[str], cwd: Path | None = None) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd or ROOT)).returncode

def _symbols_top(top: int | None) -> List[str]:
    wl = load_watchlist()
    syms = [(d.get("symbol") or "").replace("_","").upper() for d in (wl.get("top") or []) if d.get("symbol")]
    return syms if not top else syms[:top]

def _expired_pairs(tfs: List[str]) -> List[Tuple[str,str]]:
    """Renvoie [(SYMBOL, TF)] dont la stratégie est absente/expirée."""
    all_ = load_strategies()  # applique TTL (expired flag)
    need: List[Tuple[str,str]] = []
    seen = {(k.split(":")[0], k.split(":")[1]) for k,v in all_.items()}
    # 1) marquer entrants (pas de stratégie)
    for k,v in all_.items():
        sym, tf = k.split(":")
        if v.get("expired"):
            need.append((sym, tf))
    # 2) tous les tf demandés pour les symboles watchlist si pas présents
    wl_syms = {s for s in _symbols_top(None)}
    for s in wl_syms:
        for tf in tfs:
            if (s, tf) not in seen:
                need.append((s, tf))
    # dédoublonner
    out: List[Tuple[str,str]] = []
    seen2 = set()
    for t in need:
      if t not in seen2:
        out.append(t)
        seen2.add(t)
    return out

def refresh_watchlist(top: int, score_tf: str, backfill_tfs: List[str], limit: int) -> None:
    rc = sh([
        sys.executable, "jobs/refresh_pairs.py",
        "--timeframe", score_tf,
        "--top", str(top),
        "--backfill-tfs", ",".join(backfill_tfs),
        "--limit", str(limit),
    ])
    if rc != 0:
        print(f"[maintainer] refresh_pairs.py RC={rc} (on continue)")

def backfill_symbol_tf(symbol: str, tf: str, limit: int) -> None:
    # réutilise refresh_pairs.py en ciblant la watchlist existante (simple et robuste)
    # si tu as un job backfill dédié par symbole, tu peux le remplacer ici.
    rc = sh([
        sys.executable, "jobs/refresh_pairs.py",
        "--timeframe", tf,
        "--top", "0",                 # 0 => n'altère pas le tri topN
        "--backfill-tfs", tf,
        "--limit", str(limit),
    ])
    if rc != 0:
        print(f"[maintainer] backfill {symbol}:{tf} RC={rc}")

def backtest_and_promote() -> None:
    rc = sh([sys.executable, "jobs/backtest.py", "--from-watchlist", "--tfs", "1m,5m,15m,1h"])
    if rc != 0:
        print(f"[maintainer] backtest RC={rc}")
    rc = sh([sys.executable, "jobs/promote.py", "--draft", "/notebooks/scalp_data/reports/strategies.yml.next"])
    if rc != 0:
        print(f"[maintainer] promote RC={rc}")

def run_once(top: int, score_tf: str, tfs: List[str], limit: int, sleep_between_secs: int = 2) -> None:
    # 1) refresh la watchlist TOP-N + backfill global
    refresh_watchlist(top=top, score_tf=score_tf, backfill_tfs=tfs, limit=limit)

    # 2) liste des symboles (1->N)
    syms = _symbols_top(top)
    if not syms:
        print("[maintainer] watchlist vide.")
        return

    # 3) check stratégies expirées/absentes et backfill ciblé 1..N, TF croisés
    todo = _expired_pairs(tfs)
    # on restreint aux symboles du top
    todo = [(s,tf) for (s,tf) in todo if s in syms]
    if todo:
        print(f"[maintainer] éléments à remettre à jour: {len(todo)}")
    touched = False
    for s in syms:
        for tf in tfs:
            if (s, tf) in todo:
                print(f"[maintainer] backfill ciblé {s}:{tf}")
                backfill_symbol_tf(s, tf, limit=limit)
                touched = True
                time.sleep(sleep_between_secs)

    # 4) si on a touché des données expirées -> backtest + promote
    if touched:
        print("[maintainer] lancement backtest → promote…")
        backtest_and_promote()
    else:
        print("[maintainer] rien d'expiré — skip backtest.")

def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=int(os.getenv("WL_TOP", "10")))
    ap.add_argument("--score-tf", type=str, default=os.getenv("WL_TF", "5m"))
    ap.add_argument("--tfs", type=str, default=os.getenv("BACKFILL_TFS", "1m,5m,15m"))
    ap.add_argument("--limit", type=int, default=int(os.getenv("BACKFILL_LIMIT", "1500")))
    ap.add_argument("--interval", type=int, default=int(os.getenv("MAINTAINER_INTERVAL", "43200")), help="boucle toutes les N sec (défaut 12h)")
    ap.add_argument("--once", action="store_true", help="exécute une seule passe et sort")
    ns = ap.parse_args(list(argv) if argv is not None else None)

    tfs = [t.strip() for t in ns.tfs.split(",") if t.strip()]
    if ns.once:
        run_once(ns.top, ns.score_tf, tfs, ns.limit)
        return 0

    while True:
        try:
            run_once(ns.top, ns.score_tf, tfs, ns.limit)
        except Exception as e:
            print(f"[maintainer] erreur: {e}")
        time.sleep(max(300, ns.interval))  # min 5 min
    # unreachable

if __name__ == "__main__":
    raise SystemExit(main())