#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, pandas as pd, numpy as np, time, logging

ROOT="/opt/scalp/project"
DB_A=f"{ROOT}/data/a.db"
LOG=f"{ROOT}/logs/a_ctx.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s A_CTX %(levelname)s %(message)s"
)
log=logging.getLogger("A_CTX")

# -------------------------------------------------------------
# DB
# -------------------------------------------------------------
def conn():
    c=sqlite3.connect(DB_A,timeout=5,isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# -------------------------------------------------------------
# Softmax tri-classe
# -------------------------------------------------------------
def softmax_3(x,tau=0.35):
    e_pos=np.exp(x/tau)
    e_neg=np.exp(-x/tau)
    denom=e_pos+1+e_neg
    return e_pos/denom, e_neg/denom, 1 - (e_pos+e_neg)/denom

# -------------------------------------------------------------
# Score TF (ema / macd / rsi)
# -------------------------------------------------------------
def compute_tf_score(row):
    # ema trend replacement (ema21 vs ema50)
    s_ema = np.tanh((row["ema21"] - row["ema50"]) / (row["atr"]*3 + 1e-9))

    # macd hist signal
    s_macd = np.tanh(row["macdhist"] / (abs(row["macdhist"])+1e-9))

    # rsi normalisé
    s_rsi = (row["rsi"] - 50) / 50

    # pondérations pro et simple
    w_ema = 0.45
    w_macd = 0.35
    w_rsi = 0.20

    S = (
        w_ema*s_ema +
        w_macd*s_macd +
        w_rsi*s_rsi
    ) / (w_ema+w_macd+w_rsi)

    return float(S)

# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    log.info("A_CTX START")

    c = conn()

    tf_map = {
        "5m":  ("feat_5m",  0.20),
        "15m": ("feat_15m", 0.30),
        "30m": ("feat_30m", 0.50)
    }

    # Charger les dernières valeurs par TF
    dfs={}
    for tf,(table,_) in tf_map.items():
        dfs[tf]=pd.read_sql_query(
            f"""
            SELECT instId, ts, o,h,l,c,v,
                   ema9,ema21,ema50,
                   macd,macdsignal,macdhist,
                   rsi,atr
            FROM {table}
            WHERE ts=(SELECT MAX(ts) FROM {table})
            """,
            c
        )

    # Merge sur la base 30m (référence)
    merged = dfs["30m"][["instId"]].copy()
    for tf,df in dfs.items():
        df=df.add_suffix(f"_{tf}")
        df=df.rename(columns={f"instId_{tf}":"instId"})
        merged=merged.merge(df,on="instId",how="inner")

    out=[]

    for _,row in merged.iterrows():
        inst=row["instId"]

        # Compute score for each TF
        scores={}
        for tf,_ in tf_map.items():
            r=row.filter(regex=f"_{tf}$")
            r.index = r.index.str.replace(f"_{tf}","")
            scores[tf]=compute_tf_score(r)

        # Multi-TF
        S_final = (
            scores["5m"]*0.20 +
            scores["15m"]*0.30 +
            scores["30m"]*0.50
        )

        # softmax tri class
        p_buy, p_sell, p_hold = softmax_3(S_final)

        if p_buy>=0.60:
            ctx="bullish"
        elif p_sell>=0.60:
            ctx="bearish"
        else:
            ctx="flat"

        log.info(f"{inst} ctx={ctx} S={S_final:.4f}")

        out.append((
            inst,
            int(time.time()*1000),
            scores["5m"], scores["15m"], scores["30m"],
            S_final,
            p_buy, p_sell, p_hold,
            ctx
        ))

    # write DB
    c.executemany("""
    INSERT OR REPLACE INTO ctx_A (
        instId, ts_updated,
        score_5m, score_15m, score_30m,
        score_final,
        p_buy, p_sell, p_hold,
        ctx
    )
    VALUES (?,?,?,?,?,?,?,?,?,?)
    """, out)

    log.info("A_CTX DONE")

if __name__=="__main__":
    main()

