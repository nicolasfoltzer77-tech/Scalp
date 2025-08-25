#!/usr/bin/env python3
# jobs/viewer.py
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from engine.config.loader import load_config

# ---------- utils paths ----------

def _data_root_cfg() -> Dict[str, str]:
    cfg = load_config()
    rt = cfg.get("runtime", {})
    return {
        "data_dir": rt.get("data_dir") or "/notebooks/scalp_data/data",
        "reports_dir": rt.get("reports_dir") or "/notebooks/scalp_data/reports",
    }

def _live_dir() -> Path:
    return Path(_data_root_cfg()["data_dir"]) / "live"

def _orders_csv() -> Path:
    return _live_dir() / "orders.csv"

def _signals_csv() -> Path:
    return _live_dir() / "logs" / "signals.csv"

def _watchlist_yml() -> Path:
    return Path(_data_root_cfg()["reports_dir"]) / "watchlist.yml"

def _strategies_yml() -> Path:
    # stocké en JSON lisible (extension .yml)
    return Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"

# ---------- pretty helpers ----------

def _print_table(rows: Sequence[Sequence[Any]], headers: Sequence[str] | None = None) -> None:
    if headers:
        rows = [headers, ["-"*len(h) for h in headers], *rows]
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))] if rows else []
    for r in rows:
        line = " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(r))
        print(line)

def _tail(path: Path, n: int = 20) -> List[str]:
    if not path.exists():
        return []
    try:
        # simple tail sans dépendances
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-n:]
        return [l.rstrip("\n") for l in lines]
    except Exception:
        return []

# ---------- viewers ----------

def cmd_watchlist(_: argparse.Namespace) -> int:
    p = _watchlist_yml()
    if not p.exists():
        print(f"(watchlist introuvable) {p}")
        return 1
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        print(f"(format non lisible) {p}")
        return 1
    top = doc.get("top") or []
    rows = []
    for d in top:
        rows.append([d.get("symbol",""), f"{float(d.get('vol_usd_24h',0.0)):.0f}", f"{float(d.get('atr_pct_24h',0.0))*100:.2f}%", f"{float(d.get('score',0.0)):.3f}"])
    _print_table(rows, headers=["SYMBOL","VOL_USD_24H","ATR% (approx)","SCORE"])
    return 0

def cmd_strategies(_: argparse.Namespace) -> int:
    p = _strategies_yml()
    if not p.exists():
        print(f"(strategies.yml introuvable) {p}")
        return 1
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        print(f"(format non lisible) {p}")
        return 1
    strat = doc.get("strategies") or {}
    rows = []
    for k, v in strat.items():
        rows.append([
            k,
            v.get("ema_fast",""),
            v.get("ema_slow",""),
            v.get("atr_period",""),
            v.get("trail_atr_mult",""),
            v.get("risk_pct_equity",""),
        ])
    rows.sort(key=lambda r: r[0])
    _print_table(rows, headers=["PAIR:TF","ema_fast","ema_slow","atr_period","trail_mult","risk_pct"])
    return 0

def cmd_tail_orders(ns: argparse.Namespace) -> int:
    p = _orders_csv()
    lines = _tail(p, ns.lines)
    if not lines:
        print(f"(pas de contenu) {p}")
        return 0
    print(f"# {p}")
    for ln in lines:
        print(ln)
    return 0

def cmd_tail_signals(ns: argparse.Namespace) -> int:
    p = _signals_csv()
    lines = _tail(p, ns.lines)
    if not lines:
        print(f"(pas de contenu) {p}")
        return 0
    print(f"# {p}")
    for ln in lines:
        print(ln)
    return 0

def cmd_status(_: argparse.Namespace) -> int:
    dr = _data_root_cfg()
    print("=== STATUS ===")
    print("DATA_DIR    :", dr["data_dir"])
    print("REPORTS_DIR :", dr["reports_dir"])
    wl = _watchlist_yml()
    st = _strategies_yml()
    od = _orders_csv()
    sg = _signals_csv()
    print("watchlist   :", wl, "(ok)" if wl.exists() else "(absent)")
    print("strategies  :", st, "(ok)" if st.exists() else "(absent)")
    print("orders.csv  :", od, f"(tail {len(_tail(od,1)) and 'non-vide' or 'vide'})")
    print("signals.csv :", sg, f"(tail {len(_tail(sg,1)) and 'non-vide' or 'vide'})")
    return 0

# ---------- main ----------

def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mini viewer scalp")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Résumé chemins + présence des fichiers").set_defaults(func=cmd_status)
    sub.add_parser("watchlist", help="Affiche la watchlist top N").set_defaults(func=cmd_watchlist)
    sub.add_parser("strategies", help="Affiche les stratégies promues").set_defaults(func=cmd_strategies)

    p1 = sub.add_parser("orders", help="Tail des ordres (paper ou réel)")
    p1.add_argument("--lines", type=int, default=30)
    p1.set_defaults(func=cmd_tail_orders)

    p2 = sub.add_parser("signals", help="Tail des signaux prix live")
    p2.add_argument("--lines", type=int, default=30)
    p2.set_defaults(func=cmd_tail_signals)

    ns = ap.parse_args(argv)
    return int(ns.func(ns))

if __name__ == "__main__":
    raise SystemExit(main())