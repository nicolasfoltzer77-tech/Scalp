#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import os, json, argparse
from typing import List, Dict

RISK_POLICIES = {
    "conservative": {"pf": 1.4, "mdd": 0.15, "trades": 35},
    "normal":       {"pf": 1.3, "mdd": 0.20, "trades": 30},
    "aggressive":   {"pf": 1.2, "mdd": 0.30, "trades": 25},
}

def load_summary(path: str) -> Dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"summary.json introuvable: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def score_row(r: Dict) -> float:
    """
    Petite 'note' lisible:
    - PF pèse fort (+)
    - MDD pénalise (--)
    - Sharpe (+)
    - Win rate (+ léger)
    """
    pf = float(r.get("pf", 0))
    mdd = float(r.get("mdd", 1))
    sh  = float(r.get("sharpe", 0))
    wr  = float(r.get("wr", 0))
    # Note simple, stable pour trier
    return pf*2.0 + sh*0.5 + wr*0.5 - mdd*1.5

def pass_policy(r: Dict, mode: str) -> bool:
    pol = RISK_POLICIES.get(mode, RISK_POLICIES["normal"])
    return (r.get("pf",0) >= pol["pf"]) and (r.get("mdd",1) <= pol["mdd"]) and (r.get("trades",0) >= pol["trades"])

def explain_fail(r: Dict, mode: str) -> str:
    pol = RISK_POLICIES.get(mode, RISK_POLICIES["normal"])
    bad = []
    if r.get("pf",0) < pol["pf"]:
        bad.append(f"PF {r.get('pf',0):.2f} < {pol['pf']:.2f}")
    if r.get("mdd",1) > pol["mdd"]:
        bad.append(f"MDD {r.get('mdd',1):.2%} > {pol['mdd']:.0%}")
    if r.get("trades",0) < pol["trades"]:
        bad.append(f"TR {r.get('trades',0)} < {pol['trades']}")
    return "; ".join(bad) if bad else "OK"

def print_table(rows: List[Dict], k: int, risk_mode: str):
    try:
        from rich.table import Table
        from rich.console import Console
        from rich import box
        c = Console()
        t = Table(title=f"TOP {k} — meilleurs backtests (risk_mode={risk_mode})", box=box.SIMPLE_HEAVY)
        for col in ("rank","pair","tf","PF","MDD","TR","WR","Sharpe","Note","Status"):
            t.add_column(col, justify="right" if col in ("rank","PF","MDD","TR","WR","Sharpe","Note") else "left")
        for i, r in enumerate(rows[:k], 1):
            status = "PASS" if pass_policy(r, risk_mode) else f"FAIL: {explain_fail(r, risk_mode)}"
            t.add_row(
                str(i),
                r["pair"],
                r["tf"],
                f"{r.get('pf',0):.2f}",
                f"{r.get('mdd',0):.2%}",
                f"{r.get('trades',0)}",
                f"{r.get('wr',0):.2%}",
                f"{r.get('sharpe',0):.2f}",
                f"{score_row(r):.2f}",
                status
            )
        c.print(t)
    except Exception:
        # Fallback texte
        header = "RANK\tPAIR\tTF\tPF\tMDD\tTR\tWR\tSharpe\tNote\tStatus"
        print(header)
        for i, r in enumerate(rows[:k], 1):
            status = "PASS" if pass_policy(r, risk_mode) else f"FAIL: {explain_fail(r, risk_mode)}"
            print(f"{i}\t{r['pair']}\t{r['tf']}\t{r.get('pf',0):.2f}\t{r.get('mdd',0):.2%}\t{r.get('trades',0)}\t{r.get('wr',0):.2%}\t{r.get('sharpe',0):.2f}\t{score_row(r):.2f}\t{status}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", default="/notebooks/scalp_data/reports", help="Dossier des reports")
    ap.add_argument("--k", type=int, default=20, help="Nombre de lignes à afficher")
    ap.add_argument("--sort", default="score", choices=["score","pf","sharpe","mdd","trades"], help="Clé de tri")
    ap.add_argument("--risk-mode", default=None, help="Override du risk_mode (sinon lu dans summary.json)")
    ap.add_argument("--min-trades", type=int, default=0, help="Filtre minimal trades")
    args = ap.parse_args()

    summary_path = os.path.join(args.reports_dir, "summary.json")
    sm = load_summary(summary_path)
    rows = sm.get("rows", [])
    if not rows:
        print("Aucune ligne dans summary.json — lance d'abord jobs/backtest.py")
        return

    # risk mode
    risk_mode = args.risk_mode or sm.get("risk_mode", "normal")

    # filtre trades min
    if args.min_trades > 0:
        rows = [r for r in rows if r.get("trades", 0) >= args.min_trades]

    # tri
    if args.sort == "score":
        rows.sort(key=score_row, reverse=True)
    elif args.sort == "pf":
        rows.sort(key=lambda r: (r.get("pf",0), -r.get("mdd",1), r.get("sharpe",0)), reverse=True)
    elif args.sort == "sharpe":
        rows.sort(key=lambda r: (r.get("sharpe",0), r.get("pf",0)), reverse=True)
    elif args.sort == "mdd":
        rows.sort(key=lambda r: r.get("mdd",1))  # plus petit d'abord
    elif args.sort == "trades":
        rows.sort(key=lambda r: r.get("trades",0), reverse=True)

    print_table(rows, args.k, risk_mode)

    # résumé de passage
    passed = [r for r in rows if pass_policy(r, risk_mode)]
    print(f"\nRésumé: {len(passed)} PASS / {len(rows)} total "
          f"(policy={risk_mode}: PF≥{RISK_POLICIES[risk_mode]['pf']} MDD≤{int(RISK_POLICIES[risk_mode]['mdd']*100)}% TR≥{RISK_POLICIES[risk_mode]['trades']})")

if __name__ == "__main__":
    main()