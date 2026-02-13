#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RECORDER — ANALYSE UNITAIRE PAR UID (DESK-GRADE)

- lecture seule recorder.db
- aucune logique métier
- analyse FSM complète d'un trade
"""

import sqlite3
from pathlib import Path

DB = Path("/opt/scalp/project/data/recorder.db")

UID = "BTC-sell-173146-eb55"   # <<< UID À ANALYSER ICI

# ============================================================
# UTILS
# ============================================================

def conn():
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row
    return c

def fmt(v, n=4):
    if v is None:
        return "NA"
    if isinstance(v, float):
        return f"{v:+.{n}f}"
    return str(v)

def print_block(title):
    print("\n" + title)
    print("=" * len(title))

# ============================================================
# LOAD
# ============================================================

c = conn()

trade = c.execute("""
    SELECT *
    FROM recorder
    WHERE uid=?
""", (UID,)).fetchone()

if not trade:
    print(f"UID introuvable : {UID}")
    exit(1)

steps = c.execute("""
    SELECT *
    FROM recorder_steps
    WHERE uid=?
    ORDER BY step, ts_exec
""", (UID,)).fetchall()

# ============================================================
# RÉSUMÉ GLOBAL
# ============================================================

print_block(f"TRADE — {UID}")

dur = (
    (trade["ts_close"] - trade["ts_open"]) / 1000.0
    if trade["ts_open"] and trade["ts_close"] else None
)

mfe = trade["mfe_atr"]
mae = trade["mae_atr"]
admitted = mfe is not None and mfe >= 0.30

print(f"Instrument     : {trade['instId']} ({trade['side']})")
print(f"Type / Mode    : {trade['type_signal']} / {trade['dec_mode']}")
print(f"PNL net        : {fmt(trade['pnl_realized'])}")
print(f"Durée          : {fmt(dur,1)}s")
print(f"MFE (ATR)      : {fmt(mfe)}")
print(f"MAE (ATR)      : {fmt(mae)}")
print(f"Admission      : {'ADMISE' if admitted else 'REJETÉE'}")
print(f"Nb partial     : {trade['nb_partial']}")
print(f"Nb pyramide    : {trade['nb_pyramide']}")

# ============================================================
# FSM — TIMELINE
# ============================================================

print_block("FSM — DÉROULÉ CHRONOLOGIQUE")

if not steps:
    print("Aucune étape enregistrée.")
else:
    for s in steps:
        print(
            f"step={s['step']:>2} | "
            f"{s['exec_type']:<8} | "
            f"mfe={fmt(s['mfe_atr'])} | "
            f"mae={fmt(s['mae_atr'])} | "
            f"golden={s['golden']} | "
            f"{s['reason']}"
        )

# ============================================================
# DIAGNOSTIC DESK
# ============================================================

print_block("DIAGNOSTIC DESK")

if not admitted:
    print("❌ Trade REJETÉ (jamais admis)")
    print("→ Toute exploitation est structurellement négative.")
else:
    print("✅ Trade ADMIS (edge théorique validé)")

if trade["nb_partial"] > 0:
    print("• Partial exécuté : réduction du risque ✔")
else:
    print("• Aucun partial : exposition pleine jusqu'à la fin")

if trade["nb_pyramide"] > 0:
    print("• Pyramide exécutée : allocation progressive")
else:
    print("• Aucune pyramide")

if trade["pnl_realized"] < 0:
    print("⚠️ Trade perdant")
    if admitted:
        print("→ perte malgré admission : problème d'exploitation / timing sortie")
    else:
        print("→ perte normale (trade rejeté)")
else:
    print("💰 Trade gagnant")

c.close()

