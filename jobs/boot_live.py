#!/usr/bin/env python3
# jobs/boot_live.py
"""
Boot 'tout‑en‑un' :
- refresh_pairs (TOP N) + backfill multi‑TF
- seed_strategies (EXPERIMENTAL, observe‑only) pour tous les symbols de la watchlist
- lance bot.py

Usage simple :
  python jobs/boot_live.py

Options :
  --top 10                nombre de paires à garder en watchlist (défaut 10)
  --timeframe 5m          TF de scoring pour la watchlist (défaut 5m)
  --backfill-tfs 1m,5m    Tfs à backfiller (défaut 1m,5m,15m)
  --limit 1500            nb de candles par backfill TF (défaut 1500)
  --seed-tfs 1m,5m        Tfs pour lesquelles on seed les stratégies (défaut 1m)
  --ttl-bars-exp 120      TTL en nb de barres pour EXPERIMENTAL (défaut 120)
  --no-seed               ne pas seeder (si déjà promues)
  --just-run              ne pas rafraichir/seed, juste lancer bot.py
"""

from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path

from engine.config.loader import load_config

cfg = load_config()
wl = cfg.get("watchlist", {})
mt = cfg.get("maintainer", {})

top = ns.top or int(wl.get("top", 10))
timeframe = ns.timeframe or str(wl.get("score_tf", "5m"))
backfill_tfs = ns.backfill_tfs or ",".join(wl.get("backfill_tfs", ["1m","5m","15m"]))
limit = ns.limit or int(wl.get("backfill_limit", 1500))
seed_tfs = ns.seed_tfs or ",".join(mt.get("seed_tfs", ["1m"]))
ttl_bars_exp = ns.ttl_bars_exp or int(mt.get("ttl_bars_experimental", 120))

ROOT = Path(__file__).resolve().parents[1]

def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT)).returncode

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=int(os.getenv("WL_TOP", "10")))
    ap.add_argument("--timeframe", type=str, default=os.getenv("WL_TF", "5m"))
    ap.add_argument("--backfill-tfs", type=str, default=os.getenv("BACKFILL_TFS", "1m,5m,15m"))
    ap.add_argument("--limit", type=int, default=int(os.getenv("BACKFILL_LIMIT", "1500")))
    ap.add_argument("--seed-tfs", type=str, default=os.getenv("SEED_TFS", "1m"))
    ap.add_argument("--ttl-bars-exp", type=int, default=int(os.getenv("SEED_TTL_EXP", "120")))
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--just-run", action="store_true")
    ns = ap.parse_args(argv)

    if not ns.just_run:
        # 1) refresh watchlist + backfill
        rc = run([
            sys.executable, "jobs/refresh_pairs.py",
            "--timeframe", ns.timeframe,
            "--top", str(ns.top),
            "--backfill-tfs", ns.backfill_tfs,
            "--limit", str(ns.limit),
        ])
        if rc != 0:
            print(f"[boot] refresh_pairs.py a retourné {rc} — on continue quand même (mode dégradé).")

        # 2) seed strategies EXPERIMENTAL/observe-only pour tous les symbols watchlist
        if not ns.no_seed:
            rc = run([
                sys.executable, "jobs/seed_strategies.py",
                "--tfs", ns.seed_tfs,
                "--ttl-bars-exp", str(ns.ttl_bars_exp),
            ])
            if rc != 0:
                print(f"[boot] seed_strategies.py a retourné {rc} — on continue quand même (mode observe-only).")

    # 3) lancer le bot
    rc = run([sys.executable, "bot.py"])
    return rc

if __name__ == "__main__":
    raise SystemExit(main())