#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import math
import time
import hashlib

DB_REC = "/opt/scalp/project/data/recorder.db"
DB_H   = "/opt/scalp/project/data/h.db"

ROLLING_MAX = 200
MIN_TRADES  = 5

# -----------------------------
# Utils
# -----------------------------
def conn(path, ro=False):
    uri = f"file:{path}?mode=ro" if ro else path
    c = sqlite3.connect(uri, uri=ro, timeout=5)
    c.execute("PRAGMA busy_timeout=5000;")
    return c

def bucket_score(x):
    if x is None: return "mid"
    if x < 0.2: return "vlow"
    if x < 0.4: return "low"
    if x < 0.6: return "mid"
    if x < 0.8: return "high"
    return "vhigh"

def time_bucket(ts_ms):
    t = time.gmtime(ts_ms / 1000)
    wd = t.tm_wday  # 0=lundi
    h  = t.tm_hour

    if wd >= 5:
        return "weekend"
    if wd == 0 and h < 12:
        return "mon_am"
    if wd == 0:
        return "mon_pm"
    if wd == 4 and h < 12:
        return "fri_am"
    if wd == 4:
        return "fri_pm"
    return "wk_mid"

def setup_hash(parts):
    return hashlib.sha1("|".join([str(p) for p in parts]).encode()).hexdigest()

def sigmoid(x):
    return 1 / (1 + math.exp(-x)) if x is not None else 0.5

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

# -----------------------------
# Main
# -----------------------------
def main():

    r = conn(DB_REC, ro=True)
    h = conn(DB_H)

    rows = r.execute("""
        SELECT
            instId,
            side,
            ctx_close,
            score_C,
            score_S,
            pnl_net,
            ts_open,
            ts_close
        FROM recorder
        WHERE ts_recorded IS NOT NULL
          AND pnl_net IS NOT NULL
        ORDER BY ts_close DESC
    """).fetchall()

    buckets = {}

    for instId, side, ctx, sc, ss, pnl, ts_open, ts_close in rows:

        if ts_open is None or pnl is None:
            continue

        tb  = time_bucket(ts_open)
        scb = bucket_score(sc)
        ssb = bucket_score(ss)

        # regime, tf_ref volontairement absents (NULL)
        key = (instId, side, ctx, None, None, tb, scb, ssb)
        buckets.setdefault(key, []).append(pnl)

        if len(buckets[key]) >= ROLLING_MAX:
            continue

    now = int(time.time() * 1000)

    for key, pnls in buckets.items():
        if len(pnls) < MIN_TRADES:
            continue

        wins   = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        n = len(pnls)
        win_rate = len(wins) / n
        avg_pnl  = sum(pnls) / n
        expectancy = avg_pnl
        pf = (sum(wins) / abs(sum(losses))) if losses else 3.0

        dd = 0
        peak = 0
        cum = 0
        for p in pnls:
            cum += p
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        max_dd = abs(dd)

        win_n = clamp(win_rate)
        exp_n = sigmoid(expectancy)
        pf_n  = math.tanh(pf / 3)

        raw  = 0.4 * win_n + 0.4 * exp_n + 0.2 * pf_n
        conf = min(1.0, math.log(n + 1) / math.log(50))
        score_H = clamp(raw * conf)

        shash = setup_hash(key)

        h.execute("""
            INSERT OR REPLACE INTO h_stats VALUES (
                ?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,
                ?,?
            )
        """, (
            shash,
            *key,
            n,
            win_rate,
            expectancy,
            avg_pnl,
            pf,
            max_dd,
            score_H,
            now
        ))

    h.commit()
    r.close()
    h.close()

if __name__ == "__main__":
    main()

