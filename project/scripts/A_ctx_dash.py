#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime

DB = "/opt/scalp/project/data/a.db"

def conn():
    return sqlite3.connect(DB, timeout=3)

def fmt_ts_ms(ts_ms):
    if ts_ms is None:
        return "n/a"
    try:
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts_ms)

def main():
    c = conn()

    # On lit directement ctx_A (photo actuelle complète)
    rows = c.execute("""
        SELECT instId,
               ctx,
               score_final,
               ts_updated,
               score_5m,
               score_15m,
               score_30m
        FROM ctx_A
        ORDER BY score_final DESC;
    """).fetchall()

    if not rows:
        print("===== CTX DASH (A) =====")
        print("Aucun contexte disponible (ctx_A vide).")
        return

    # Synthèse par catégorie
    nb_bull = sum(1 for r in rows if r[1] == "bullish")
    nb_bear = sum(1 for r in rows if r[1] == "bearish")
    nb_flat = sum(1 for r in rows if r[1] == "flat")

    print("===== CTX DASH (A) =====\n")

    print("--- Synthèse ---")
    print(" nb_bullish  nb_bearish  nb_flat")
    print(f"{nb_bull:>11}{nb_bear:>12}{nb_flat:>9}\n")

    print("--- Exemples (2 par catégorie) ---")
    print("   type   instId      score_final")

    # Top 2 bullish
    bulls = [r for r in rows if r[1] == "bullish"][:5]
    for instId, ctx, score_final, *_ in bulls:
        print(f"bullish {instId:<8} {score_final}")

    # Top 2 bearish
    bears = [r for r in rows if r[1] == "bearish"][:5]
    for instId, ctx, score_final, *_ in bears:
        print(f"bearish {instId:<8} {score_final}")

    # Top 2 flat
    flats = [r for r in rows if r[1] == "flat"][:2]
    for instId, ctx, score_final, *_ in flats:
        print(f"flat    {instId:<8} {score_final}")

    print("\n--- Contexte complet ---")
    print("  instId           ts_local              ctx     score_final   score_5m     score_15m    score_30m")

if __name__ == "__main__":
    main()

