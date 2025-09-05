#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
why_hold.py — Diagnostique des HOLD dans signals.csv

But
----
Identifier, pour chaque couple (sym, tf), quelles composantes gardent l'état HOLD
et résumer les derniers états observés.

Entrées
-------
- CSV: /opt/scalp/var/dashboard/signals.csv (modifiable via $SCALP_SIGNALS_CSV)
- Colonnes attendues: ts,sym,tf,side,details
  * details: "sma_cross_fast=HOLD;rsi_reversion=HOLD;ema_trend=HOLD" (clé=valeur ; séparées par ';')

Usage
-----
  why_hold.py [SYMS] [TFS] [LIMIT] [--top N]

  SYMS  : liste séparée par virgules, ex "BTCUSDT,ETHUSDT" (par défaut: tous)
  TFS   : liste séparée par virgules, ex "1m,5m,15m" (par défaut: tous)
  LIMIT : nb max de lignes récentes à considérer (défaut: 2000)
  --top : nb de paires (sym,tf) à afficher en détail (défaut: 10)

Exemples
--------
  why_hold.py
  why_hold.py "BTCUSDT,ETHUSDT" "1m,5m" 3000 --top 5
"""

import csv
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, Tuple, List

CSV_PATH = os.environ.get("SCALP_SIGNALS_CSV", "/opt/scalp/var/dashboard/signals.csv")

def parse_args(argv: List[str]):
    syms = None
    tfs = None
    limit = 2000
    top = 10

    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = [a for a in argv[1:] if a.startswith("--")]

    if len(args) >= 1 and args[0]:
        syms = [s.strip() for s in args[0].split(",") if s.strip()]
    if len(args) >= 2 and args[1]:
        tfs = [t.strip() for t in args[1].split(",") if t.strip()]
    if len(args) >= 3 and args[2]:
        try:
            limit = int(args[2])
        except ValueError:
            pass

    for f in flags:
        if f.startswith("--top"):
            parts = f.split()
            if len(parts) == 2 and parts[1].isdigit():
                top = int(parts[1])
            elif "=" in f:
                try:
                    top = int(f.split("=", 1)[1])
                except Exception:
                    pass
    return syms, tfs, limit, top

def parse_details(s: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not s:
        return out
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip().upper()
    return out

def read_rows(path: str) -> List[Dict[str, str]]:
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        return list(r)

def main():
    syms, tfs, limit, top = parse_args(sys.argv)
    try:
        rows = read_rows(CSV_PATH)
    except FileNotFoundError:
        print(f"[ERR] CSV introuvable: {CSV_PATH}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERR] Lecture CSV: {e}")
        sys.exit(2)

    # Garde uniquement les N dernières lignes
    rows = rows[-limit:]

    # Filtrage
    if syms:
        rows = [r for r in rows if (r.get("sym") or r.get("symbol")) in syms]
    if tfs:
        rows = [r for r in rows if (r.get("tf") or r.get("timeframe")) in tfs]

    if not rows:
        print("Aucune ligne après filtrage.")
        sys.exit(0)

    # Agrégations
    global_sides = Counter()
    by_pair_sides: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    by_pair_blocks: Dict[Tuple[str, str], Counter] = defaultdict(Counter)  # composantes==HOLD
    last_samples: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)

    for r in rows:
        sym = r.get("sym") or r.get("symbol") or ""
        tf = r.get("tf") or r.get("timeframe") or ""
        side = (r.get("side") or r.get("signal") or "").upper()
        details = r.get("details") or r.get("entry") or ""

        global_sides[side] += 1
        by_pair = (sym, tf)
        by_pair_sides[by_pair][side] += 1

        d = parse_details(details)
        # Considère comme "bloquant" toute composante qui vaut HOLD
        for k, v in d.items():
            if v == "HOLD":
                by_pair_blocks[by_pair][k] += 1

        # Conserve un petit historique récent pour affichage
        if len(last_samples[by_pair]) < 5:
            last_samples[by_pair].append(
                dict(ts=r.get("ts", ""), side=side, details=details)
            )

    # Classement des paires (celles avec le plus de HOLD en tête)
    order = sorted(
        by_pair_sides.keys(),
        key=lambda p: by_pair_sides[p]["HOLD"],
        reverse=True,
    )

    # En-tête
    uniq_pairs = len(by_pair_sides)
    print("=== WHY HOLD • Résumé ===")
    print(f"CSV: {CSV_PATH}")
    print(f"Lignes considérées: {len(rows)}  |  Paires (sym,tf): {uniq_pairs}")
    print("Global sides:", dict(global_sides))
    if syms:
        print("Filtre SYMS:", ",".join(syms))
    if tfs:
        print("Filtre TFS:", ",".join(tfs))
    print()

    # Détail top N
    print(f"=== Détail des {min(top, len(order))} paires avec le plus de HOLD ===")
    for pair in order[:top]:
        sym, tf = pair
        sides = by_pair_sides[pair]
        blocks = by_pair_blocks.get(pair, Counter())
        print(f"\n— {sym} @ {tf}")
        print("  sides:", dict(sides))
        if blocks:
            print("  composantes HOLD (compte):", dict(blocks.most_common()))
        else:
            print("  composantes HOLD (compte): {}")
        # mini-preview
        samples = last_samples.get(pair, [])
        if samples:
            print("  récents:")
            for s in samples:
                print(f"    ts={s['ts']} side={s['side']} details={s['details']}")
        else:
            print("  récents: (aucun)")

    # Synthèse: quelles composantes bloquent le plus globalement ?
    comp_global = Counter()
    for c in by_pair_blocks.values():
        comp_global.update(c)
    if comp_global:
        print("\n=== Composantes les plus BLOQUANTES (global) ===")
        print(dict(comp_global.most_common()))
    else:
        print("\n=== Composantes les plus BLOQUANTES (global) === {}")

if __name__ == "__main__":
    main()
