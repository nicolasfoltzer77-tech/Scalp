#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time, logging, traceback
import statistics

ROOT="/opt/scalp/project"
DB_T=f"{ROOT}/data/t.db"
DB_TR=f"{ROOT}/data/trigger.db"
DB_W=f"{ROOT}/data/wticks.db"

LOG=f"{ROOT}/logs/wticks.log"
logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s WTICKS %(levelname)s %(message)s"
)
log=logging.getLogger("WTICKS")

def conn(path):
    c=sqlite3.connect(path,timeout=3,isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    return c

def fetch_tasks():
    c=conn(DB_TR)
    rows=c.execute("""
        SELECT uid, instId_raw, ts_signal, price_signal
        FROM v_wticks_tasks
        WHERE status='pending'
    """).fetchall()
    return rows

def fetch_ticks(instId_raw, ts_signal):
    c=conn(DB_T)
    t_min = ts_signal - 10_000
    t_max = ts_signal + 30_000
    rows=c.execute("""
        SELECT ts, price, bid, ask, q_buy, q_sell
        FROM ticks
        WHERE instId=? AND ts BETWEEN ? AND ?
        ORDER BY ts ASC
    """,(instId_raw, t_min, t_max)).fetchall()
    return rows

def compute_metrics(rows, price_signal, ts_signal):
    if not rows:
        return None

    prices=[r[1] for r in rows]
    ts=[r[0] for r in rows]
    minp=min(prices)
    maxp=max(prices)
    meanp=sum(prices)/len(prices)
    varp=statistics.pvariance(prices) if len(prices)>1 else 0.0

    # pic : max prix
    peak_price=maxp
    peak_ts = rows[prices.index(maxp)][0]
    delta_t = peak_ts - ts_signal
    delta_pct = (peak_price - price_signal)/price_signal if price_signal>0 else 0.0

    # pression OF simple = somme(q_buy - q_sell)
    pressure=sum([r[4]-r[5] for r in rows])

    return (peak_ts, peak_price, delta_t, delta_pct,
            minp, maxp, meanp, varp, pressure)

def save(uid, instId_raw, ts_signal, metrics):
    (peak_ts, peak_price, delta_t, delta_pct,
     minp, maxp, meanp, varp, pressure)=metrics

    ts_now=int(time.time()*1000)
    c=conn(DB_W)

    c.execute("""
        INSERT OR REPLACE INTO wticks_extended (
            uid, instId_raw, ts_signal,
            peak_ts, peak_price,
            delta_t_ms, delta_price_pct,
            window_min_price, window_max_price,
            window_mean_price, window_var_price,
            pressure_bias,
            ts_created, ts_updated
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,(uid,instId_raw,ts_signal,
         peak_ts,peak_price,
         delta_t,delta_pct,
         minp,maxp,meanp,varp,
         pressure,
         ts_now,ts_now))

def mark_done(uid):
    ts=int(time.time()*1000)
    c=conn(DB_TR)
    c.execute("""
        UPDATE wticks_tasks
        SET status='done', ts_updated=?
        WHERE uid=?
    """,(ts,uid))

def main():
    while True:
        try:
            tasks=fetch_tasks()
            for uid,instId_raw,ts_signal,price_signal in tasks:
                ticks = fetch_ticks(instId_raw, ts_signal)
                metrics=compute_metrics(ticks, price_signal, ts_signal)
                if metrics:
                    save(uid,instId_raw,ts_signal,metrics)
                mark_done(uid)
                log.info(f"[DONE] WTICKS {uid}")
        except Exception as e:
            log.error(f"[ERR] {e}\n{traceback.format_exc()}")

        time.sleep(0.5)

if __name__=="__main__":
    main()

