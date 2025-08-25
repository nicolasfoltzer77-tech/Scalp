#!/usr/bin/env python3
# jobs/boot_live.py
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from engine.config.loader import load_config

ROOT = Path(__file__).resolve().parents[1]

def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT)).returncode

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--timeframe", type=str, default=None)
    ap.add_argument("--backfill-tfs", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed-tfs", type=str, default=None)
    ap.add_argument("--ttl-bars-exp", type=int, default=None)
    ap.add_argument("--no-seed", action="store_true")
    ap.add_argument("--just-run", action="store_true")
    ns = ap.parse_args(argv)

    cfg = load_config()
    wl = cfg.get("watchlist", {})
    mt = cfg.get("maintainer", {})

    top = ns.top or int(wl.get("top", 10))
    timeframe = ns.timeframe or str(wl.get("score_tf", "5m"))
    backfill_tfs = ns.backfill_tfs or ",".join(wl.get("backfill_tfs", ["1m","5m","15m"]))
    limit = ns.limit or int(wl.get("backfill_limit", 1500))
    seed_tfs = ns.seed_tfs or ",".join(mt.get("seed_tfs", ["1m"]))
    ttl_bars_exp = ns.ttl_bars_exp or int(mt.get("ttl_bars_experimental", 120))

    if not ns.just_run:
        rc = run([sys.executable, "-m", "jobs.refresh_pairs",
                  "--timeframe", timeframe, "--top", str(top),
                  "--backfill-tfs", backfill_tfs, "--limit", str(limit)])
        if rc != 0:
            print(f"[boot] refresh_pairs RC={rc} (continue)")

        if not ns.no_seed:
            rc = run([sys.executable, "-m", "jobs.seed_strategies",
                      "--tfs", seed_tfs, "--ttl-bars-exp", str(ttl_bars_exp)])
            if rc != 0:
                print(f"[boot] seed_strategies RC={rc} (continue)")

    return run([sys.executable, "bot.py"])

if __name__ == "__main__":
    raise SystemExit(main())