#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, logging, time
import pandas as pd
import numpy as np

ROOT = "/opt/scalp/project"
DB_A  = f"{ROOT}/data/a.db"
LOG   = f"{ROOT}/logs/a_feat.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s A_FEAT %(levelname)s %(message)s"
)
log = logging.getLogger("A_FEAT")

# ==========================================================
# DB
# ==========================================================
def conn():
    c = sqlite3.connect(DB_A, timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# ==========================================================
# INDICATORS
# ==========================================================
def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    high_low = df["h"] - df["l"]
    high_close = (df["h"] - df["c"].shift()).abs()
    low_close = (df["l"] - df["c"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def macd(df):
    ema12 = ema(df["c"], 12)
    ema26 = ema(df["c"], 26)
    macd_line = ema12 - ema26
    signal = ema(macd_line, 9)
    hist = macd_line - signal
    return macd_line, signal, hist

def bollinger(df, period=20):
    mid = df["c"].rolling(period).mean()
    std = df["c"].rolling(period).std()
    up = mid + 2 * std
    low = mid - 2 * std
    width = (up - low) / mid
    return mid, up, low, width

# ==========================================================
# PURGE
# ==========================================================
H = 500
L = 150

def purge_table(co, table, inst):
    cnt = co.execute(f"SELECT COUNT(*) FROM {table} WHERE instId=?", (inst,)).fetchone()[0]
    if cnt <= H:
        return
    rows = co.execute(
        f"SELECT ts FROM {table} WHERE instId=? ORDER BY ts DESC LIMIT ? OFFSET ?",
        (inst, H, L)
    ).fetchall()
    if not rows:
        return
    cutoff = rows[-1][0]
    co.execute(f"DELETE FROM {table} WHERE instId=? AND ts < ?", (inst, cutoff))
    log.info(f"{inst} PURGE {table}: kept {H}")

# ==========================================================
# BUILD FEATURES FOR ONE TF
# ==========================================================
def build_tf(co, tf):
    ohlcv = f"ohlcv_{tf}"
    feat  = f"feat_{tf}"

    coins = [r[0] for r in co.execute(f"SELECT DISTINCT instId FROM {ohlcv}")]
    for inst in coins:

        df = pd.read_sql_query(
            f"SELECT * FROM {ohlcv} WHERE instId=? ORDER BY ts ASC",
            co,
            params=(inst,)
        )

        if len(df) < 50:
            continue

        df["ema9"]  = ema(df["c"], 9)
        df["ema20"] = ema(df["c"], 20)
        df["ema50"] = ema(df["c"], 50)
        df["rsi"]   = rsi(df["c"])
        df["atr"]   = atr(df)
        df["macd"], df["macdsignal"], df["macdhist"] = macd(df)
        df["bb_mid"], df["bb_up"], df["bb_low"], df["bb_width"] = bollinger(df)
        df["mom"]   = df["c"].diff(10)
        df["roc"]   = df["c"].pct_change(10)
        df["slope"] = df["c"].rolling(20).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0])

        last_ts_feat = co.execute(f"SELECT MAX(ts) FROM {feat} WHERE instId=?", (inst,)).fetchone()[0]
        last_ts_feat = last_ts_feat if last_ts_feat else 0

        new_df = df[df["ts"] > last_ts_feat]
        if new_df.empty:
            continue

        insert_rows = []
        for _, r in new_df.iterrows():
            insert_rows.append((
                inst, int(r.ts),
                float(r.o), float(r.h), float(r.l), float(r.c), float(r.v),
                float(r.ema9), float(r.ema20), float(r.ema50),
                float(r.rsi) if not np.isnan(r.rsi) else None,
                float(r.atr) if not np.isnan(r.atr) else None,
                float(r.macd), float(r.macdsignal), float(r.macdhist),
                float(r.bb_mid), float(r.bb_up), float(r.bb_low), float(r.bb_width),
                float(r.mom) if not np.isnan(r.mom) else None,
                float(r.roc) if not np.isnan(r.roc) else None,
                float(r.slope) if not np.isnan(r.slope) else None
            ))

        co.executemany(
            f"""
            INSERT OR REPLACE INTO {feat} VALUES (
              ?, ?, ?,?,?,?,?, 
              ?,?,?,?,?,
              ?,?,?,?,
              ?,?,?,?,
              ?,?,?
            )
            """,
            insert_rows
        )

        log.info(f"{inst} {tf} → {len(insert_rows)}")
        purge_table(co, feat, inst)

# ==========================================================
# MAIN
# ==========================================================
def main():
    log.info("A_FEAT START")
    co = conn()

    for tf in ["5m", "15m", "30m"]:
        build_tf(co, tf)

    log.info("A_FEAT DONE")


if __name__ == "__main__":
    main()

