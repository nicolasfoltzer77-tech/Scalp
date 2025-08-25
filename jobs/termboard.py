#!/usr/bin/env python3
# jobs/termboard.py
from __future__ import annotations

import argparse, os, time, json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

# ----- couleurs/affichage -------
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich import box

# ----- config / chemins ---------
def _paths() -> Dict[str, Path]:
    try:
        from engine.config.loader import load_config
        cfg = load_config()
        r = cfg.get("runtime", {})
        droot = Path(r.get("data_dir") or "/notebooks/scalp_data/data")
        rroot = Path(r.get("reports_dir") or "/notebooks/scalp_data/reports")
        return {"DATA": droot, "REPORTS": rroot, "STRAT_YML": Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"}
    except Exception:
        root = Path(os.getenv("DATA_ROOT", "/notebooks/scalp_data"))
        return {"DATA": root / "data", "REPORTS": root / "reports", "STRAT_YML": Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"}

def _csv_path(sym: str, tf: str, DATA: Path) -> Path:
    return DATA / "ohlcv" / f"{sym}USDT" / f"{tf}.csv"

def _strategies_map(STRAT_YML: Path) -> Dict[str, Dict]:
    # strategies.yml est stocké en JSON lisible (extension .yml)
    try:
        return (json.loads(STRAT_YML.read_text(encoding="utf-8"))).get("strategies", {})  # type: ignore
    except Exception:
        return {}

@dataclass
class Cell:
    text: str
    color: str

def _status_for(sym: str, tf: str, DATA: Path, STRATS: Dict[str, Dict], max_age_mult: int) -> Cell:
    """
    Codes:
      MIS (noir)  : fichier absent
      OLD (rouge) : trop vieux
      DAT (jaune) : ok data mais pas de stratégie promue
      OK  (vert)  : data récente + stratégie promue
    """
    p = _csv_path(sym, tf, DATA)
    if not p.exists():
        return Cell("MIS", "grey50")

    # fraicheur: age max = multiple du TF
    now = time.time()
    mult = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
    }.get(tf, 300)
    max_age = max_age_mult * mult
    age = now - p.stat().st_mtime
    if age > max_age:
        return Cell("OLD", "red")

    key = f"{sym}USDT:{tf}"
    if key not in STRATS:
        return Cell("DAT", "yellow3")

    return Cell("OK", "green3")

def _build_table(symbols: List[str], tfs: List[str], DATA: Path, STRATS: Dict[str, Dict], max_age_mult: int) -> Table:
    tbl = Table(box=box.SIMPLE_HEAVY, expand=False)
    tbl.add_column("PAIR", justify="left")
    for tf in tfs:
        tbl.add_column(tf, justify="center")

    stats = {"MIS": 0, "OLD": 0, "DAT": 0, "OK": 0}
    for s in symbols:
        row: List[str] = [s]
        for tf in tfs:
            c = _status_for(s, tf, DATA, STRATS, max_age_mult)
            stats[c.text] += 1
            row.append(f"[{c.color}]{c.text}[/{c.color}]")
        tbl.add_row(*row)

    legend = "[grey50]MIS[/] no data • [red]OLD[/] stale • [yellow3]DAT[/] data no strat • [green3]OK[/] ready"
    caption = f"{legend}\nstats • MIS={stats['MIS']} OLD={stats['OLD']} DAT={stats['DAT']} OK={stats['OK']}"
    tbl.caption = caption
    return tbl

def main() -> int:
    ap = argparse.ArgumentParser(description="Termboard (état data/stratégies)")
    ap.add_argument("--symbols", default="ETH,BTC,SOL,XRP,LINK,ADA,DOGE,BNB,LTC")
    ap.add_argument("--tfs", default="1m,5m,15m")
    ap.add_argument("--refresh", type=float, default=2.0)
    ap.add_argument("--age-mult", type=int, default=5, help="multiple de TF accepté avant 'OLD'")
    args = ap.parse_args()

    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    tfs = [t.strip() for t in args.tfs.split(",") if t.strip()]
    PATHS = _paths()
    DATA, STRAT_YML = PATHS["DATA"], PATHS["STRAT_YML"]

    console = Console()
    with Live(console=console, refresh_per_second=int(1/max(0.1, args.refresh))):
        while True:
            STRATS = _strategies_map(STRAT_YML)
            title = f"=== ORCHESTRATOR ===\nDATA_DIR={DATA}\nexec_enabled=0  •  refresh={args.refresh}s  •  tfs={','.join(tfs)}"
            table = _build_table(syms, tfs, DATA, STRATS, args.age_mult)
            console.clear()
            console.print(Panel(table, title=title, border_style="cyan"))
            time.sleep(args.refresh)

if __name__ == "__main__":
    raise SystemExit(main())