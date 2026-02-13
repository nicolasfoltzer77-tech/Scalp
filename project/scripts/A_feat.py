#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, logging, time
import numpy as np
import pandas as pd

ROOT = "/opt/scalp/project"
DB_OA = f"{ROOT}/data/oa.db"
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
def conn(path):
    c = sqlite3.connect(path, timeout=10, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    return c

# ==========================================================
# INDICATEURS
# ==========================================================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = up.rolling(period).mean() / down.rolling(period).mean()
    return 100 - 100 / (1 + rs)

def macd_line(c, fast=12, slow=26):
    return ema(c, fast) - ema(c, slow)

def atr(df, period=14):
    tr = np.maximum(df["h"] - df["l"],
                    np.maximum((df["h"] - df["c"].shift()).abs(),
                               (df["l"] - df["c"].shift()).abs()))
    return tr.rolling(period).mean()

def bollinger(c, period=20, mult=2):
    mid = c.rolling(period).mean()
    std = c.rolling(period).std()
    up = mid + mult * std
    low = mid - mult * std
    return mid, up, low

# ==========================================================
# LOAD OA OHLCV
# ==========================================================
def load_ohlcv(tf):
    table = f"ohlcv_{tf}"
    co = conn(DB_OA)
    df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY instId, ts", co)
    co.close()
    return df

# ==========================================================
# BUILD FEAT
# ==========================================================
def build_tf(df, tf, coa):
    """
    df : OHLCV complet (5m/15m/30m)
    coa : connexion a.db
    """
    log.info(f"TF {tf}: start")

    feats_table = f"feat_{tf}"

    # Table
    coa.execute(f"""
    CREATE TABLE IF NOT EXISTS {feats_table}(
        instId TEXT,
        ts INTEGER,
        o REAL, h REAL, l REAL, c REAL, v REAL,
        ema21 REAL, ema50 REAL,
        rsi REAL,
        macd REAL,
        atr REAL,
        bb_mid REAL, bb_up REAL, bb_low REAL,
        ctx TEXT,
        PRIMARY KEY(instId, ts)
    );
    """)

    insts = df["instId"].unique()

    for inst in insts:
        d = df[df.instId == inst].copy()
        if len(d) < 60:
            continue

        d["ema21"] = ema(d["c"], 21)
        d["ema50"] = ema(d["c"], 50)
        d["rsi"]   = rsi(d["c"], 14)
        d["macd"]  = macd_line(d["c"])
        d["atr"]   = atr(d)
        d["bb_mid"], d["bb_up"], d["bb_low"] = bollinger(d["c"])

        # soft context baseline
        ctx = []
        for i in range(len(d)):
            if d["ema21"].iloc[i] > d["ema50"].iloc[i]:
                ctx.append("bullish")
            elif d["ema21"].iloc[i] < d["ema50"].iloc[i]:
                ctx.append("bearish")
            else:
                ctx.append("neutral")
        d["ctx"] = ctx

        rows = d[[
            "instId","ts","o","h","l","c","v",
            "ema21","ema50","rsi","macd","atr",
            "bb_mid","bb_up","bb_low","ctx"
        ]].values.tolist()

        coa.executemany(
            f"INSERT OR REPLACE INTO {feats_table} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows
        )

        # purge
        cut = coa.execute(
            f"SELECT ts FROM {feats_table} WHERE instId=? ORDER BY ts DESC LIMIT 1 OFFSET 150",
            (inst,)
        ).fetchone()
        if cut:
            cutoff = cut[0]
            coa.execute(
                f"DELETE FROM {feats_table} WHERE instId=? AND ts < ?",
                (inst, cutoff)
            )

    log.info(f"TF {tf}: done")

# ==========================================================
# MAIN
# ==========================================================
def main():
    log.info("A_FEAT START")

    coa = conn(DB_A)

    # load OA
    df5  = load_ohlcv("5m")
    df15 = load_ohlcv("15m")
    df30 = load_ohlcv("30m")

    # compute 3 TF
    build_tf(df5,  "5m",  coa)
    build_tf(df15, "15m", coa)
    build_tf(df30, "30m", coa)

    coa.commit()
    coa.close()

    log.info("A_FEAT DONE")

if __name__ == "__main__":
    main()

