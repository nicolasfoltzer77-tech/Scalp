#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import pandas as pd
import numpy as np
import ta
import logging

ROOT   = "/opt/scalp/project"
DB_U   = f"{ROOT}/data/universe.db"
DB_OA  = f"{ROOT}/data/oa.db"
DB_A   = f"{ROOT}/data/a.db"
LOG    = f"{ROOT}/logs/a_feat_builder.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s A_FEAT %(levelname)s %(message)s"
)
log = logging.getLogger("A_FEAT")

# -------------------------------------------------------------
# DB
# -------------------------------------------------------------
def conn(path):
    c = sqlite3.connect(path, timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# -------------------------------------------------------------
# INDICATEURS ROBUSTES
# -------------------------------------------------------------
def compute_indicators(df):
    MIN_ROWS = 20

    if len(df) < MIN_ROWS:
        df = df.copy()
        df["ema9"]  = np.nan
        df["ema21"] = np.nan
        df["ema50"] = np.nan
        df["macd"]       = np.nan
        df["macdsignal"] = np.nan
        df["macdhist"]   = np.nan
        df["rsi"] = np.nan
        df["atr"] = np.nan
        return df

    df["ema9"]  = ta.trend.EMAIndicator(df["c"], window=9).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(df["c"], window=21).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["c"], window=50).ema_indicator()

    macd = ta.trend.MACD(df["c"])
    df["macd"]       = macd.macd()
    df["macdsignal"] = macd.macd_signal()
    df["macdhist"]   = macd.macd_diff()

    df["rsi"] = ta.momentum.RSIIndicator(df["c"], window=14).rsi()

    try:
        df["atr"] = ta.volatility.average_true_range(
            df["h"], df["l"], df["c"], window=14
        )
    except Exception as e:
        log.warning(f"ATR error → NaN: {e}")
        df["atr"] = np.nan

    return df

# -------------------------------------------------------------
# LOAD OHLCV OA
# -------------------------------------------------------------
def load_ohlcv(instId, tf):
    table = f"ohlcv_{tf}"
    sql = f"""
        SELECT
            ts,
            open  AS o,
            high  AS h,
            low   AS l,
            close AS c,
            volume AS v
        FROM {table}
        WHERE instId = ?
        ORDER BY ts ASC
    """
    c = conn(DB_OA)
    df = pd.read_sql_query(sql, c, params=(instId,))
    if df.empty:
        return None

    df.set_index("ts", inplace=True)
    return df

# -------------------------------------------------------------
# PURGE FEAT_xm
# -------------------------------------------------------------
def purge_feat(tf):
    table = f"feat_{tf}"
    c = conn(DB_A)

    insts = c.execute(f"SELECT DISTINCT instId FROM {table}").fetchall()

    for (instId,) in insts:
        try:
            rows = c.execute(f"""
                SELECT ts FROM {table}
                WHERE instId=?
                ORDER BY ts DESC
                LIMIT 150
            """, (instId,)).fetchall()

            if len(rows) < 150:
                continue

            oldest_keep = rows[-1][0]

            c.execute(f"""
                DELETE FROM {table}
                WHERE instId=? AND ts < ?
            """, (instId, oldest_keep))

        except Exception as e:
            log.error(f"purge {instId} {tf} error: {e}")

# -------------------------------------------------------------
# SAVE FEATURES
# -------------------------------------------------------------
def save_features(instId, tf, df):
    table = f"feat_{tf}"
    df2 = df.copy()
    df2 = df2.reset_index()  # ts devient colonne
    df2["instId"] = instId

    df2 = df2[[
        "instId", "ts",
        "o", "h", "l", "c", "v",
        "ema9", "ema21", "ema50",
        "macd", "macdsignal", "macdhist",
        "rsi", "atr"
    ]]

    c = conn(DB_A)

    # Remplacement propre → évite le blocage PK
    for row in df2.itertuples(index=False, name=None):
        try:
            c.execute(f"""
                INSERT OR REPLACE INTO {table}(
                    instId, ts,
                    o,h,l,c,v,
                    ema9,ema21,ema50,
                    macd,macdsignal,macdhist,
                    rsi,atr
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, row)
        except Exception as e:
            log.error(f"{instId} {tf} insert error: {e}")

# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    log.info("A_FEAT START")

    cu = conn(DB_U)
    insts = [x[0] for x in cu.execute(
        "SELECT instId FROM v_universe_tradable ORDER BY instId"
    ).fetchall()]

    for inst in insts:
        for tf in ("5m", "15m", "30m"):

            try:
                df = load_ohlcv(inst, tf)
                if df is None or df.empty:
                    log.warning(f"{inst} {tf}: NO OHLCV")
                    continue

                df_feat = compute_indicators(df)
                save_features(inst, tf, df_feat)
                log.info(f"{inst} {tf}: FEAT OK")

            except Exception as e:
                log.error(f"{inst} {tf}: ERROR {e}")

    # PURGE
    for tf in ("5m", "15m", "30m"):
        purge_feat(tf)

    log.info("A_FEAT END")

if __name__ == "__main__":
    main()

