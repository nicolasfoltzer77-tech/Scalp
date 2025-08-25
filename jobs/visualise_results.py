#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, json, argparse
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", required=True, help="/notebooks/scalp_data/reports")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    sm_path = Path(args.reports_dir) / "summary.json"
    if not sm_path.exists():
        print("summary.json absent — lance d'abord jobs/backtest.py"); return

    with open(sm_path, "r", encoding="utf-8") as f:
        sm = json.load(f)
    rows = sm.get("rows", [])
    rows.sort(key=lambda r: (r.get("pf",0), -r.get("mdd",1), r.get("sharpe",0)), reverse=True)

    try:
        from rich.table import Table
        from rich.console import Console
        from rich import box
        c = Console()
        t = Table(title="Backtest — meilleurs résultats", box=box.SIMPLE_HEAVY)
        for col in ("pair","tf","pf","mdd","trades","wr","sharpe","equity"):
            t.add_column(col.upper())
        for r in rows[:args.top]:
            t.add_row(
                r["pair"], r["tf"],
                f"{r['pf']:.2f}", f"{r['mdd']:.2%}",
                str(r["trades"]), f"{r['wr']:.2%}",
                f"{r['sharpe']:.2f}", f"{r.get('equity',1.0):.3f}"
            )
        c.print(t)
        c.print(f"[dim]Sélectionnés:[/dim] {', '.join(sm.get('selected', []))}")
    except Exception:
        print("PAIR\tTF\tPF\tMDD\tTRADES\tWR\tSHARPE\tEQ")
        for r in rows[:args.top]:
            print(f"{r['pair']}\t{r['tf']}\t{r['pf']:.2f}\t{r['mdd']:.2%}\t{r['trades']}\t{r['wr']:.2%}\t{r['sharpe']:.2f}\t{r.get('equity',1.0):.3f}")

if __name__ == "__main__":
    main()