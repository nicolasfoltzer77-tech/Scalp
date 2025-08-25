#!/usr/bin/env python3
# jobs/termboard.py
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

# --- dépendance légère pour l'affichage terminal ---
# (si "rich" n'est pas dispo, fais:  pip install rich)
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich import box


# ---------- chemins / config ----------
def _paths() -> Dict[str, Path]:
    """
    Récupère data_dir, reports_dir depuis la config si possible.
    Fallback sur /notebooks/scalp_data/.
    """
    try:
        from engine.config.loader import load_config
        cfg = load_config()
        rt = cfg.get("runtime", {}) or {}
        data = Path(rt.get("data_dir") or "/notebooks/scalp_data/data")
        reports = Path(rt.get("reports_dir") or "/notebooks/scalp_data/reports")
    except Exception:
        root = Path("/notebooks/scalp_data")
        data, reports = root / "data", root / "reports"

    strat = Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"
    return {"DATA": data, "REPORTS": reports, "STRAT": strat}


def _csv_path(sym: str, tf: str, data_dir: Path) -> Path:
    return data_dir / "ohlcv" / f"{sym}USDT" / f"{tf}.csv"


def _load_strats(strat_yml: Path) -> Dict[str, Dict]:
    """
    strategies.yml stocké en JSON lisible (extension .yml).
    Retourne un dict: { "PAIR:TF": { ... } }.
    """
    try:
        return (json.loads(strat_yml.read_text(encoding="utf-8"))).get("strategies", {})  # type: ignore
    except Exception:
        return {}


# ---------- statut cellule ----------
@dataclass
class Cell:
    text: str
    color: str  # code rich (ex: 'red', 'green3', ...)


def _status(sym: str, tf: str, data_dir: Path, strats: Dict[str, Dict], age_mult: int) -> Cell:
    """
    Codes:
      MIS (gris) : CSV manquant
      OLD (rouge): CSV trop ancien
      DAT (jaune): CSV ok mais stratégie absente
      OK  (vert) : CSV ok + stratégie promue (non expirée)
    """
    p = _csv_path(sym, tf, data_dir)
    if not p.exists():
        return Cell("MIS", "grey50")

    # fraicheur: seuil = age_mult × TF
    tf_sec = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900,
        "30m": 1800, "1h": 3600, "4h": 14400
    }.get(tf, 300)
    max_age = age_mult * tf_sec
    age = time.time() - p.stat().st_mtime
    if age > max_age:
        return Cell("OLD", "red")

    key = f"{sym}USDT:{tf}"
    s = strats.get(key)
    if s and not s.get("expired"):
        return Cell("OK", "green3")

    return Cell("DAT", "yellow3")


# ---------- tableau ----------
def _build_table(symbols: List[str], tfs: List[str], data_dir: Path,
                 strats: Dict[str, Dict], age_mult: int) -> Table:
    tbl = Table(box=box.SIMPLE_HEAVY, expand=False)
    tbl.add_column("PAIR", justify="left")
    for tf in tfs:
        tbl.add_column(tf, justify="center")

    stats = {"MIS": 0, "OLD": 0, "DAT": 0, "OK": 0}
    for s in symbols:
        row = [s]
        for tf in tfs:
            c = _status(s, tf, data_dir, strats, age_mult)
            stats[c.text] += 1
            row.append(f"[{c.color}]{c.text}[/{c.color}]")
        tbl.add_row(*row)

    legend = "[grey50]MIS[/]=no data • [red]OLD[/]=stale • [yellow3]DAT[/]=data no strat • [green3]OK[/]=ready"
    tbl.caption = f"{legend}\n" \
                  f"stats • MIS={stats['MIS']} OLD={stats['OLD']} DAT={stats['DAT']} OK={stats['OK']}"
    return tbl


# ---------- main ----------
def main() -> int:
    ap = argparse.ArgumentParser(description="Termboard: état pairs×TF (console)")
    ap.add_argument("--symbols", default="ETH,BTC,SOL,XRP,LINK,ADA,DOGE,BNB,LTC",
                    help="Liste de tickers (sans USDT), ex: ETH,BTC,SOL")
    ap.add_argument("--tfs", default="1m,5m,15m", help="Timeframes séparés par des virgules")
    ap.add_argument("--refresh", type=float, default=2.0, help="Période de rafraîchissement (s)")
    ap.add_argument("--age-mult", type=int, default=5, help="Multiple de TF accepté avant OLD")
    args = ap.parse_args()

    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]

    P = _paths()
    DATA, STRAT = P["DATA"], P["STRAT"]

    console = Console()
    # calcul raisonnable pour Live.refresh_per_second
    rps = max(1, int(1 / max(0.2, args.refresh)))

    with Live(console=console, refresh_per_second=rps):
        while True:
            strats = _load_strats(STRAT)
            title = (
                f"=== ORCHESTRATOR (TUI) ===\n"
                f"DATA_DIR={DATA}\n"
                f"refresh={args.refresh}s  tfs={','.join(tfs)}  age_mult×TF={args.age_mult}"
            )
            table = _build_table(syms, tfs, DATA, strats, args.age_mult)
            console.clear()
            console.print(Panel(table, title=title, border_style="cyan"))
            time.sleep(args.refresh)


if __name__ == "__main__":
    raise SystemExit(main())