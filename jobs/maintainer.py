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
from typing import Dict, List, Set, Tuple

from engine.config.loader import load_config
from engine.config.watchlist import load_watchlist
from engine.config.strategies import load_strategies

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("maintainer")

# --------- couleurs / rendu compact ----------
COLORS = {
    "black": "\x1b[30m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "orange": "\x1b[33m",
    "reset": "\x1b[0m",
}

def _short_sym(s: str) -> str:
    s = s.upper().replace("_", "")
    return s[:-4] if s.endswith("USDT") else s

def _color_block(color: str, text: str) -> str:
    c = COLORS.get(color, "")
    r = COLORS["reset"]
    return f"{c}{text}{r}"

def _render_status_table(symbols: List[str], tfs: List[str],
                         todo: Set[tuple[str, str]], strategies: dict) -> str:
    header = ["PAIR"] + [tf for tf in tfs]
    rows = []
    present = {(k.split(":")[0], k.split(":")[1]) for k in strategies.keys()}
    expired = {(k.split(":")[0], k.split(":")[1]) for k, v in strategies.items() if v.get("expired")}

    for s in symbols:
        line = [_short_sym(s)]
        for tf in tfs:
            key = (s, tf)
            if key in todo:
                cell = _color_block("orange", "UPD")
            elif key in expired:
                cell = _color_block("red", "OLD")
            elif key in present:
                cell = _color_block("green", "OK ")
            else:
                cell = _color_block("black", "-- ")
            line.append(cell)
        rows.append(line)

    widths = [max(len(str(r[i])) for r in ([header] + rows)) for i in range(len(header))]
    def fmt(row): return " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(header)))
    table = [fmt(header), fmt(["-" * w for w in widths]), *[fmt(r) for r in rows]]
    return "\n".join(table)

def _paint_live_table(symbols: List[str], tfs: List[str]) -> None:
    """Dessine le tableau sur stdout (sans passer par le logger) pour un rendu 'live'."""
    try:
        strategies = load_strategies()
        todo = set(_expired_pairs(tfs))
        table = _render_status_table(symbols, tfs, todo, strategies)
        # Effacer l'écran + curseur en haut
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write("[maintainer] État (PAIR×TF)\n")
        sys.stdout.write(table + "\n")
        sys.stdout.flush()
    except Exception:
        # si souci, on ne casse pas la boucle
        pass

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
    fh.setLevel(logging.INFO); ch.setLevel(logging.INFO)
    log.addHandler(fh); log.addHandler(ch)
    log.info("Logger prêt • fichier=%s", logs_dir / "maintainer.log")

# ------------------------ helpers ------------------------

def run_cmd(args: List[str]) -> tuple[int, str, str]:
    """Lance une commande en capturant stdout/stderr. Retourne (rc, out, err)."""
    p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if out: log.info("stdout: %s", out)
    if err: log.warning("stderr: %s", err)
    return p.returncode, out, err

def _symbols_top(top: int | None) -> List[str]:
    wl = load_watchlist()
    syms = [(d.get("symbol") or "").replace("_", "").upper()
            for d in (wl.get("top") or []) if d.get("symbol")]
    return syms if not top else syms[:top]

def _expired_pairs(tfs: List[str]) -> List[Tuple[str, str]]:
    """(symbol, tf) expirés ou manquants par rapport à strategies.yml et watchlist."""
    all_ = load_strategies()
    need: List[Tuple[str, str]] = []
    present = {(k.split(":")[0], k.split(":")[1]) for k in all_.keys()}

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
    for x in need:
        if x not in seen:
            out.append(x); seen.add(x)
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
    rc, _, _ = run_cmd([
        sys.executable, "-m", "jobs.refresh_pairs",
        "--timeframe", tf,
        "--top", "0",
        "--backfill-tfs", tf,
        "--limit", str(limit),
    ])
    ok = (rc == 0)
    if ok:  log.info("backfill OK: %s:%s", symbol, tf)
    else:   log.warning("backfill FAIL: %s:%s (rc=%s)", symbol, tf, rc)
    return ok

def backtest_and_promote() -> None:
    rc, _, _ = run_cmd([sys.executable, "-m", "jobs.backtest",
                        "--from-watchlist", "--tfs", "1m,5m,15m,1h"])
    if rc != 0:
        log.warning("backtest RC=%s", rc)
    draft = "/notebooks/scalp_data/reports/strategies.yml.next"
    rc, _, _ = run_cmd([sys.executable, "-m", "jobs.promote", "--draft", draft])
    if rc != 0:
        log.warning("promote RC=%s", rc)
    _summary_strategies()

def _summary_strategies() -> None:
    try:
        strat: Dict[str, Dict] = load_strategies()
        total = len(strat)
        expired = sum(1 for v in strat.values() if v.get("expired"))
        by_tf: Dict[str, int] = {}
        for k in strat.keys():
            try: _, tf = k.split(":")
            except ValueError: tf = "?"
            by_tf[tf] = by_tf.get(tf, 0) + 1
        tf_str = ", ".join(f"{tf}:{n}" for tf, n in sorted(by_tf.items()))
        log.info("STRATEGIES • total=%d • expirées=%d • par_tf=(%s)", total, expired, tf_str)
    except Exception as e:
        log.warning("summary strategies impossible: %s", e)

# ------------------------ pipeline ------------------------

def run_once(top: int, score_tf: str, tfs: List[str], limit: int,
             sleep_between_secs: float,
             live_table: bool,
             live_interval: float) -> None:
    log.info("=== RUN ONCE === top=%s score_tf=%s tfs=%s limit=%s", top, score_tf, tfs, limit)

    refresh_watchlist(top=top, score_tf=score_tf, backfill_tfs=tfs, limit=limit)

    syms = _symbols_top(top)
    if not syms:
        log.warning("Watchlist vide — stop.")
        return

    # premier rendu
    todo = [(s, tf) for (s, tf) in _expired_pairs(tfs) if s in syms]
    try:
        strat = load_strategies()
        table = _render_status_table(syms, tfs, set(todo), strat)
        log.info("\n%s", table)
    except Exception:
        pass
    if live_table:
        _paint_live_table(syms, tfs)

    touched = False
    last_live = time.time()

    for s in syms:
        for tf in tfs:
            if (s, tf) in todo:
                ok = backfill_symbol_tf(s, tf, limit=limit)
                touched = touched or ok
            # rafraîchissement live périodique
            if live_table and (time.time() - last_live) >= live_interval:
                _paint_live_table(syms, tfs)
                last_live = time.time()
            time.sleep(max(0.0, sleep_between_secs))

    if live_table:
        _paint_live_table(syms, tfs)

    if touched:
        log.info("backtest → promote…")
        backtest_and_promote()
    else:
        log.info("rien d'expiré — skip backtest.")
        _summary_strategies()

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
        "sleep_between": float(mt.get("sleep_between_secs", 0.5)),
        "live": bool(mt.get("live_table", True)),
        "live_interval": float(mt.get("live_interval_secs", 2.0)),
    }

def main(argv=None) -> int:
    _setup_logging()
    ap = argparse.ArgumentParser(description="Mainteneur TOP‑N watchlist + backfill + backtest/promotion (tableau live)")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--score-tf", type=str, default=None)
    ap.add_argument("--tfs", type=str, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--interval", type=int, default=None, help="intervalle boucle (sec)")
    ap.add_argument("--once", action="store_true", help="exécute une seule passe et sort")
    ap.add_argument("--sleep-between", type=float, default=None, help="pause entre backfills (sec)")
    ap.add_argument("--live-table", action="store_true", help="active le tableau live (sinon lecture depuis config)")
    ap.add_argument("--no-live-table", action="store_true", help="force la désactivation du live")
    ap.add_argument("--live-interval", type=float, default=None, help="rafraîchissement du live (sec)")

    ns = ap.parse_args(argv)

    base = _cfg_vals()
    top = ns.top if ns.top is not None else base["top"]
    score_tf = ns.score_tf if ns.score_tf is not None else base["score_tf"]
    tfs = [t.strip() for t in (ns.tfs or ",".join(base["tfs"])).split(",") if t.strip()]
    limit = ns.limit if ns.limit is not None else base["limit"]
    interval = ns.interval if ns.interval is not None else base["interval"]
    sleep_between = ns.sleep_between if ns.sleep_between is not None else base["sleep_between"]

    # live-table : priorité aux flags CLI
    if ns.live_table: live = True
    elif ns.no_live_table: live = False
    else: live = base["live"]
    live_interval = ns.live_interval if ns.live_interval is not None else base["live_interval"]

    if ns.once:
        run_once(top, score_tf, tfs, limit, sleep_between, live, live_interval)
        return 0

    while True:
        try:
            run_once(top, score_tf, tfs, limit, sleep_between, live, live_interval)
        except Exception:
            log.exception("erreur maintainer")
        time.sleep(max(300, interval))

if __name__ == "__main__":
    raise SystemExit(main())