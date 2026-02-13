#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, time, logging, statistics
import math

ROOT = "/opt/scalp/project"
DB_OB = f"{ROOT}/data/ob.db"
DB_B  = f"{ROOT}/data/b.db"
DB_U  = f"{ROOT}/data/universe.db"

LOG = f"{ROOT}/logs/b_feat.log"
logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s B_FEAT %(levelname)s %(message)s"
)
log = logging.getLogger("B_FEAT")

# ---------------------------------------------------------
# DB
# ---------------------------------------------------------
def conn(path):
    c = sqlite3.connect(path, timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# ---------------------------------------------------------
# LOAD UNIVERSE
# ---------------------------------------------------------
def load_universe():
    cu = conn(DB_U)
    xs = [r[0] for r in cu.execute("SELECT instId FROM v_universe_tradable;")]
    cu.close()
    return xs

# ---------------------------------------------------------
# LAST TS IN FEAT
# ---------------------------------------------------------
def last_ts_feat(co_b, table, inst):
    r = co_b.execute(
        f"SELECT MAX(ts) FROM {table} WHERE instId=?",
        (inst,)
    ).fetchone()
    return r[0] if r and r[0] else 0


# ---------------------------------------------------------
# GET NEW ROWS ONLY
# ---------------------------------------------------------
def load_ohlcv_incremental(tf, inst, last_ts):
    table = f"ohlcv_{tf}"
    co = conn(DB_OB)
    rows = co.execute(
        f"SELECT ts,o,h,l,c,v FROM {table} WHERE instId=? AND ts>? ORDER BY ts ASC",
        (inst, last_ts)
    ).fetchall()
    co.close()
    return rows


# ---------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------
def ema(series, period):
    if len(series) < period:
        return None
    k = 2 / (period + 1)
    ema_val = series[0]
    for price in series[1:]:
        ema_val = price * k + ema_val * (1 - k)
    return ema_val

def rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i - 1]
        if diff >= 0:
            gains.append(diff)
        else:
            losses.append(-diff)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period if sum(losses) != 0 else 0.0000001
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def atr(highs, lows, closes, period=14):
    if len(highs) < period + 1:
        return None
    trs = []
    for i in range(1, period + 1):
        prev = closes[-i - 1]
        tr = max(
            highs[-i] - lows[-i],
            abs(highs[-i] - prev),
            abs(lows[-i] - prev)
        )
        trs.append(tr)
    return sum(trs) / period

def adx(highs, lows, closes, period=14):
    if len(highs) < period + 2:
        return None, None, None
    plus_dm = []
    minus_dm = []
    tr_list = []
    for i in range(1, period + 1):
        up = highs[-i] - highs[-i - 1]
        dn = lows[-i - 1] - lows[-i]
        plus_dm.append(up if up > dn and up > 0 else 0)
        minus_dm.append(dn if dn > up and dn > 0 else 0)
        tr = max(
            highs[-i] - lows[-i],
            abs(highs[-i] - closes[-i - 1]),
            abs(lows[-i] - closes[-i - 1])
        )
        tr_list.append(tr)
    atr_v = sum(tr_list) / period
    if atr_v == 0:
        return None, None, None
    plus_di = (sum(plus_dm) / atr_v) * 100
    minus_di = (sum(minus_dm) / atr_v) * 100
    dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-6) * 100
    adx_v = dx
    return plus_di, minus_di, adx_v

# ---------------------------------------------------------
# COMPUTE FEAT ROW
# ---------------------------------------------------------
def compute_feat(rows):
    if len(rows) < 30:
        return None

    closes = [r[4] for r in rows]
    highs  = [r[2] for r in rows]
    lows   = [r[3] for r in rows]

    ema9  = ema(closes[-9:], 9)
    ema12 = ema(closes[-12:], 12)
    ema21 = ema(closes[-21:], 21)
    ema26 = ema(closes[-26:], 26)
    ema50 = ema(closes[-50:], 50)

    macd = (ema12 - ema26) if ema12 and ema26 else None
    macdsig = None
    macdhist = None

    rsi_v = rsi(closes, 14)
    atr_v = atr(highs, lows, closes, 14)

    bb_mid = statistics.mean(closes[-20:]) if len(closes) >= 20 else None
    bb_std = statistics.pstdev(closes[-20:]) if len(closes) >= 20 else None
    bb_up  = bb_mid + 2 * bb_std if bb_mid and bb_std else None
    bb_low = bb_mid - 2 * bb_std if bb_mid and bb_std else None
    bb_width = (bb_up - bb_low) if bb_up and bb_low else None

    # momentum
    mom = closes[-1] - closes[-10] if len(closes) >= 10 else None
    roc = (closes[-1] / closes[-10] - 1) * 100 if len(closes) >= 10 else None

    # slope
    slope = (closes[-1] - closes[-5]) / 5 if len(closes) >= 5 else None

    # ctx dummy
    ctx = "unknown"

    plus_di, minus_di, adx_v = adx(highs, lows, closes)

    return (
        rows[-1][0],   # ts
        rows[-1][1], rows[-1][2], rows[-1][3], rows[-1][4], rows[-1][5],  # o,h,l,c,v
        ema9, ema12, ema21, ema26, ema50,
        macd, macdsig, macdhist,
        rsi_v, atr_v,
        bb_mid, bb_std, bb_up, bb_low, bb_width,
        mom, roc, slope,
        ctx,
        plus_di, minus_di, adx_v
    )


# ---------------------------------------------------------
# PURGE
# ---------------------------------------------------------
def purge(co_b, table, inst, H, L):
    cnt = co_b.execute(
        f"SELECT COUNT(*) FROM {table} WHERE instId=?",
        (inst,)
    ).fetchone()[0]

    if cnt <= H:
        return

    rows = co_b.execute(
        f"SELECT ts FROM {table} WHERE instId=? ORDER BY ts DESC LIMIT ? OFFSET ?",
        (inst, H, L)
    ).fetchall()

    if not rows:
        return

    cutoff = rows[-1][0]

    co_b.execute(
        f"DELETE FROM {table} WHERE instId=? AND ts < ?",
        (inst, cutoff)
    )

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    log.info("B_FEAT START")

    coins = load_universe()
    co_b  = conn(DB_B)

    for inst in coins:
        for tf in ("1m", "3m", "5m"):
            table = f"feat_{tf}"
            last = last_ts_feat(co_b, table, inst)
            ohlcv = load_ohlcv_incremental(tf, inst, last)

            if not ohlcv:
                continue

            # Build rolling windows
            buf = []
            inserted = 0

            for r in ohlcv:
                buf.append(r)
                if len(buf) > 200:
                    buf.pop(0)
                feat = compute_feat(buf)
                if feat:
                    try:
                        co_b.execute(
                            f"INSERT INTO {table} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (inst,) + feat
                        )
                        inserted += 1
                    except Exception as e:
                        log.error(f"{inst} {tf} FAIL {e}")

            log.info(f"{inst} {tf} → {inserted}")

            # purge
            if tf == "1m":
                purge(co_b, table, inst, 1500, 450)
            else:
                purge(co_b, table, inst, 500, 150)

    log.info("B_FEAT DONE")

if __name__ == "__main__":
    main()

