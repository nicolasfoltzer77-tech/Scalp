#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time
from statistics import mean

DB_REC = "/opt/scalp/project/data/recorder.db"
DB_A   = "/opt/scalp/project/data/analytics.db"

def conn(path):
    c = sqlite3.connect(path, timeout=3, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    return c

# --------------------------------------------------------------------
# BUCKETS
# --------------------------------------------------------------------
def bucket_ctx(ctx, score_A):
    if ctx in ("bullish", "bearish", "flat"):
        return ctx
    return "unknown"

def bucket_hour(ts_open):
    from datetime import datetime
    h = datetime.utcfromtimestamp(ts_open/1000).hour
    if 0 <= h < 6:   return 0
    if 6 <= h < 12:  return 1
    if 12 <= h < 18: return 2
    return 3

def bucket_weekday(ts_open):
    from datetime import datetime
    wd = datetime.utcfromtimestamp(ts_open/1000).weekday()
    if wd in (1,2,3): return "tue_thu"
    if wd == 4:       return "fri"
    if wd in (5,6):   return "weekend"
    return "mon"

def bucket_atr(atr_value):
    if atr_value is None: return "unknown"
    if atr_value < 0.005: return "low"
    if atr_value < 0.015: return "mid"
    return "high"

def bucket_of(of_strength):
    if of_strength is None: return "unknown"
    if of_strength < 0.33:  return "weak"
    if of_strength < 0.66:  return "mid"
    return "strong"

# --------------------------------------------------------------------
# MAIN : CALCUL H
# --------------------------------------------------------------------
def compute_historical():
    cR = conn(DB_REC)
    cA = conn(DB_A)

    rows = cR.execute("""
        SELECT
            instId, side, reason,
            pnl_net, pnl_pct,
            ctx, score_A,
            ts_open,
            atr_signal
        FROM trades_recorded
        WHERE status='recorded'
    """).fetchall()

    groups = {}
    for instId, side, reason, pnl_net, pnl_pct, ctx, score_A, ts_open, atr_signal in rows:
        key = (instId, side, reason)
        if key not in groups:
            groups[key] = {
                "pnls": [],
                "pct": [],
                "ctx": [],
                "ts": [],
                "atr": []
            }
        groups[key]["pnls"].append(pnl_net)
        groups[key]["pct"].append(pnl_pct)
        groups[key]["ctx"].append((ctx, score_A))
        groups[key]["ts"].append(ts_open)
        groups[key]["atr"].append(atr_signal)

    cA.execute("DELETE FROM historical_scores;")

    now = int(time.time()*1000)

    for (instId, side, reason), g in groups.items():

        wins = [p for p in g["pnls"] if p > 0]
        win_rate = len(wins) / len(g["pnls"])

        pnl_avg = mean(g["pct"]) if g["pct"] else 0.0

        score_H = 0.5*win_rate + 0.5*(pnl_avg/0.01)
        if score_H < 0: score_H = 0
        if score_H > 1: score_H = 1

        ctx, scoreA = g["ctx"][-1]
        ctx_dir = bucket_ctx(ctx, scoreA)

        ts_ref = g["ts"][-1]
        hour_b = bucket_hour(ts_ref)
        wd_b   = bucket_weekday(ts_ref)

        atr_ref = g["atr"][-1]
        atr_b = bucket_atr(atr_ref)

        of_b = "unknown"

        cA.execute("""
            INSERT INTO historical_scores(
                instId, side, reason,
                win_rate, pnl_avg, score_H,
                ctx_dir, hour_bucket, weekday_bucket,
                atr_bucket, of_bucket,
                ts_updated
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            instId, side, reason,
            win_rate, pnl_avg, score_H,
            ctx_dir, hour_b, wd_b,
            atr_b, of_b,
            now
        ))

    cA.commit()
    cA.close()
    cR.close()

if __name__ == "__main__":
    compute_historical()

