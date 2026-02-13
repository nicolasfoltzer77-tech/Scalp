#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time, traceback

DB_A = "/opt/scalp/project/data/analytics.db"
DB_R = "/opt/scalp/project/data/recorder.db"

def conn(path):
    c = sqlite3.connect(path, timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    return c

# -------------------------------------------------------------------
# FETCH RECORDED TRADES (base historique)
# -------------------------------------------------------------------
def load_trades():
    c = conn(DB_R)
    rows = c.execute("""
        SELECT
            instId,
            side,
            reason,
            ctx,
            score_A,
            score_B,
            atr_signal,
            pnl_net,
            ts_signal
        FROM trades_recorded
        WHERE status = 'recorded';
    """).fetchall()

    trades = []
    for r in rows:
        inst, side, reason, ctx_dir, scoreA, scoreB, atr, pnl, ts = r

        # Buckets
        scoreC_bucket = (
            'strong' if scoreA >= 0.70 else
            'weak' if scoreA <= 0.30 else
            'mid'
        )

        scoreS_bucket = (
            'strong' if scoreB >= 0.70 else
            'weak' if scoreB <= 0.30 else
            'mid'
        )

        if atr <= 0.5:
            atr_bucket = 'low'
        elif atr <= 1.5:
            atr_bucket = 'mid'
        else:
            atr_bucket = 'high'

        # hour + weekday
        hour = int((ts // 1000) % 86400 // 3600)
        if 2 <= hour <= 10:
            hour_bucket = 1
        elif 11 <= hour <= 16:
            hour_bucket = 2
        elif 17 <= hour <= 22:
            hour_bucket = 3
        else:
            hour_bucket = 4

        weekday = int((ts // 1000) % (7*86400) // 86400)
        weekday_bucket = (
            'weekend' if weekday in (5,6) else
            'fri' if weekday == 4 else
            'mon' if weekday == 0 else
            'tue_thu'
        )

        trades.append((
            inst, side, reason, ctx_dir,
            scoreC_bucket, scoreS_bucket,
            atr_bucket, pnl, hour_bucket,
            weekday_bucket
        ))

    return trades

# -------------------------------------------------------------------
# COMPUTE SCORES
# -------------------------------------------------------------------
def compute_scores(trades):
    agg = {}

    for inst, side, reason, ctx, cB, sB, atrB, pnl, hB, wdB in trades:
        key = (inst, side, reason, ctx, cB, sB, atrB, hB, wdB)

        if key not in agg:
            agg[key] = {"wins": 0, "count": 0, "pnl_sum": 0}

        agg[key]["count"] += 1
        agg[key]["pnl_sum"] += pnl
        if pnl > 0:
            agg[key]["wins"] += 1

    rows = []
    ts_now = int(time.time() * 1000)

    for key, stats in agg.items():
        inst, side, reason, ctx, cB, sB, atrB, hB, wdB = key
        win_rate = stats["wins"] / stats["count"]
        pnl_avg  = stats["pnl_sum"] / stats["count"]

        score_H = 0.5 * win_rate + 0.5 * max(0, pnl_avg)
        score_H = max(0, min(score_H, 1))

        # booster directionnel simple
        if ctx == 'bullish' and side == 'buy':
            score_dir = 1.05
        elif ctx == 'bearish' and side == 'sell':
            score_dir = 1.05
        else:
            score_dir = 0.95

        score_H_final = max(0, min(score_H * score_dir, 1))

        rows.append((
            inst, side, reason,
            ctx, cB, sB,
            atrB, None, hB, wdB,
            win_rate, pnl_avg,
            score_H, score_H_final,
            ts_now
        ))

    return rows

# -------------------------------------------------------------------
# SAVE TO DB
# -------------------------------------------------------------------
def save(rows):
    c = conn(DB_A)
    c.executemany("""
        INSERT OR REPLACE INTO historical_scores (
            instId, side, reason,
            ctx_dir, score_C_bucket, score_S_bucket,
            atr_bucket, of_bucket,
            hour_bucket, weekday_bucket,
            win_rate, pnl_avg,
            score_H, score_H_final,
            ts_updated
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
    """, rows)

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main():
    try:
        trades = load_trades()
        rows = compute_scores(trades)
        save(rows)
        print(f"OK analytics: {len(rows)} rows updated")
    except Exception as e:
        print("ERR analytics", e, traceback.format_exc())

if __name__ == "__main__":
    main()


