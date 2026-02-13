#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
B_feat_builder.py (HYBRIDE)
- Incremental si OB OK
- Full si trou, reset, lag, oversize, incohérence
- Purge : 1m=450, 3m=150, 5m=150
- 100% aligné sur les 29 colonnes réelles de feat_xm (b.db)
"""

import sqlite3, time, logging, math, statistics

ROOT="/opt/scalp/project"
DB_OB=f"{ROOT}/data/ob.db"
DB_B =f"{ROOT}/data/b.db"
LOG  =f"{ROOT}/logs/b_feat.log"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s B_FEAT %(levelname)s %(message)s"
)
log=logging.getLogger("B_FEAT")

# =====================================================================================
# DB UTIL
# =====================================================================================

def conn(db):
    c=sqlite3.connect(db, timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c

# =====================================================================================
# INDICATEURS
# =====================================================================================

def ema(values, period):
    if len(values)<period:
        return [None]*len(values)
    k=2/(period+1)
    out=[None]*(period-1)
    s=sum(values[:period])/period
    out.append(s)
    for v in values[period:]:
        s=v*k + s*(1-k)
        out.append(s)
    return out

def rsi(values, period=14):
    if len(values)<period+1:
        return [None]*len(values)
    deltas=[values[i]-values[i-1] for i in range(1,len(values))]
    gains=[max(d,0) for d in deltas]
    losses=[abs(min(d,0)) for d in deltas]
    avg_gain=sum(gains[:period])/period
    avg_loss=sum(losses[:period])/period
    rsis=[None]*(period)
    for i in range(period, len(deltas)):
        avg_gain=(avg_gain*(period-1)+gains[i])/period
        avg_loss=(avg_loss*(period-1)+losses[i])/period
        rs = avg_gain/avg_loss if avg_loss!=0 else float("inf")
        rsis.append(100 - 100/(1+rs))
    return [None] + rsis

def atr(high, low, close, period=14):
    if len(high)<period+1:
        return [None]*len(high)
    trs=[None]
    for i in range(1,len(high)):
        trs.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
    out=[None]*period
    s=sum(trs[1:period+1])/period
    out.append(s)
    k=1/period
    for t in trs[period+1:]:
        s=s + k*(t-s)
        out.append(s)
    return out

def macd_line(values, fast=12, slow=26, signal=9):
    if len(values)<slow:
        return [None]*len(values), [None]*len(values), [None]*len(values)
    e_fast=ema(values,fast)
    e_slow=ema(values,slow)
    macd=[None if e_fast[i] is None or e_slow[i] is None else e_fast[i]-e_slow[i] for i in range(len(values))]
    valid=[m for m in macd if m is not None]
    sig=ema(valid,signal)
    sig=[None]*(len(macd)-len(sig)) + sig
    hist=[None if macd[i] is None or sig[i] is None else macd[i]-sig[i] for i in range(len(values))]
    return macd, sig, hist

def bollinger(values, period=20, std_mult=2):
    if len(values)<period:
        return ([None]*len(values),)*5
    mid=[None]*(period-1)
    stdv=[None]*(period-1)
    up=[None]*(period-1)
    low=[None]*(period-1)
    for i in range(period-1, len(values)):
        window=values[i-period+1:i+1]
        m=statistics.mean(window)
        s=statistics.pstdev(window)
        mid.append(m)
        stdv.append(s)
        up.append(m+std_mult*s)
        low.append(m-std_mult*s)
    width=[None if mid[i] is None else (up[i]-low[i]) for i in range(len(values))]
    return mid, stdv, up, low, width

def momentum(values, period=10):
    if len(values)<period:
        return [None]*len(values)
    return [None]*period + [values[i]-values[i-period] for i in range(period,len(values))]

def roc(values, period=10):
    if len(values)<period:
        return [None]*len(values)
    res=[None]*period
    for i in range(period, len(values)):
        if values[i-period]!=0:
            res.append((values[i]/values[i-period]-1)*100)
        else:
            res.append(None)
    return res

def variance(x):
    m=sum(x)/len(x)
    return sum((xi-m)**2 for xi in x)/len(x)

def covariance(x,y):
    mx=sum(x)/len(x)
    my=sum(y)/len(y)
    return sum((x[i]-mx)*(y[i]-my) for i in range(len(x)))/len(x)

def slope(values, period=12):
    if len(values)<period:
        return [None]*len(values)
    out=[None]*period
    x=list(range(period))
    for i in range(period, len(values)):
        w=values[i-period+1:i+1]
        m=covariance(x,w)/variance(x)
        out.append(m)
    return out

def adx(high, low, close, period=14):
    if len(high)<period+2:
        return ([None]*len(high),)*3

    plus_dm=[None]
    minus_dm=[None]
    tr=[None]

    for i in range(1,len(high)):
        up=high[i]-high[i-1]
        dn=low[i-1]-low[i]
        plus_dm.append(up if up>dn and up>0 else 0)
        minus_dm.append(dn if dn>up and dn>0 else 0)
        tr.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))

    spdm=[None]*period
    smdm=[None]*period
    strr=[None]*period

    spdm.append(sum(plus_dm[1:period+1]))
    smdm.append(sum(minus_dm[1:period+1]))
    strr.append(sum(tr[1:period+1]))

    for i in range(period+1, len(high)):
        spdm.append(spdm[-1] - (spdm[-1]/period) + plus_dm[i])
        smdm.append(smdm[-1] - (smdm[-1]/period) + minus_dm[i])
        strr.append(strr[-1] - (strr[-1]/period) + tr[i])

    pdi=[None]*period
    mdi=[None]*period
    dx =[None]*period

    for i in range(period, len(high)):
        trval=strr[i]
        if trval and trval!=0:
            p=100*(spdm[i]/trval)
            m=100*(smdm[i]/trval)
        else:
            p,m=None,None
        pdi.append(p)
        mdi.append(m)
        if p is not None and m is not None and (p+m)!=0:
            dx.append(abs(p-m)/(p+m)*100)
        else:
            dx.append(None)

    if len(dx)<period*2:
        adx_line=[None]*len(high)
    else:
        val=sum([d for d in dx[period:] if d is not None])/period
        adx_line=[None]*(period*2)
        adx_line.append(val)
        for d in dx[period+1:]:
            val=((period-1)*val + d)/period if d is not None else val
            adx_line.append(val)
        while len(adx_line)<len(high):
            adx_line.append(None)

    while len(pdi)<len(high):    pdi.append(None)
    while len(mdi)<len(high):    mdi.append(None)
    while len(adx_line)<len(high): adx_line.append(None)

    return pdi, mdi, adx_line

# =====================================================================================
# OB CONSISTENCY CHECKS
# =====================================================================================

def check_ob(con, table, tf_sec, max_age, max_rows):
    cur=con.cursor()
    count=cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if count==0:
        return False,"EMPTY"

    if (table=="ohlcv_1m" and count>1500) or (table!="ohlcv_1m" and count>500):
        return False,"OVERSIZE"

    ts_last=cur.execute(f"SELECT MAX(ts) FROM {table}").fetchone()[0]
    age=(int(time.time()*1000)-ts_last)/1000
    if age>max_age:
        return False,f"LAG {age}s"

    rows=cur.execute(f"SELECT ts FROM {table} ORDER BY ts").fetchall()
    ts=[x[0] for x in rows]
    expected=tf_sec*1000
    gaps=0
    for i in range(1,len(ts)):
        if ts[i]-ts[i-1] != expected:
            gaps+=1
        if gaps>1:
            return False,f"TROU {gaps}"

    return True,"OK"

# =====================================================================================
# FEATURE GENERATOR
# =====================================================================================

def build_features(ts,o,h,l,c,v):
    ema9v  = ema(c,9)
    ema12v = ema(c,12)
    ema21v = ema(c,21)
    ema26v = ema(c,26)
    ema50v = ema(c,50)

    macd_l,macd_s,macd_h = macd_line(c)
    rsi14 = rsi(c,14)
    atr14 = atr(h,l,c,14)
    bb_mid,bb_std,bb_up,bb_low,bb_width = bollinger(c)
    mom10 = momentum(c,10)
    roc10 = roc(c,10)
    slope12 = slope(c,12)
    plus_di,minus_di,adx_line = adx(h,l,c,14)

    ctx=[None]*len(ts)

    return list(zip(
        ts,o,h,l,c,v,
        ema9v,ema12v,ema21v,ema26v,ema50v,
        macd_l,macd_s,macd_h,
        rsi14,atr14,
        bb_mid,bb_std,bb_up,bb_low,bb_width,
        mom10,roc10,slope12,
        ctx,
        plus_di,minus_di,adx_line
    ))

# =====================================================================================
# FULL MODE
# =====================================================================================

def run_full():
    log.info("[FULL] rebuild complet")
    con_ob=conn(DB_OB)
    con_b =conn(DB_B)
    cur_b=con_b.cursor()

    cfg=[
        ("ohlcv_1m","feat_1m",450),
        ("ohlcv_3m","feat_3m",150),
        ("ohlcv_5m","feat_5m",150),
    ]

    for table_ob, table_feat, keep in cfg:
        log.info(f"[FULL] rebuild {table_feat}")

        rows=con_ob.execute(f"""
            SELECT instId, ts, o,h,l,c,v
            FROM {table_ob}
            ORDER BY instId, ts
        """).fetchall()

        if not rows:
            log.warning(f"[FULL] aucun data OB pour {table_ob}")
            continue

        cur_b.execute(f"DELETE FROM {table_feat}")

        # Regrouper par instId
        insts={}
        for instId,ts,o,h,l,c,v in rows:
            insts.setdefault(instId,{"ts":[],"o":[],"h":[],"l":[],"c":[],"v":[]})
            insts[instId]["ts"].append(ts)
            insts[instId]["o"].append(o)
            insts[instId]["h"].append(h)
            insts[instId]["l"].append(l)
            insts[instId]["c"].append(c)
            insts[instId]["v"].append(v)

        for instId,dd in insts.items():
            feat=build_features(dd["ts"],dd["o"],dd["h"],dd["l"],dd["c"],dd["v"])
            data=[(instId,)+x for x in feat]

            cur_b.executemany(f"""
                INSERT OR REPLACE INTO {table_feat}(
                    instId, ts, o,h,l,c,v,
                    ema9,ema12,ema21,ema26,ema50,
                    macd,macdsignal,macdhist,
                    rsi,atr,
                    bb_mid,bb_std,bb_up,bb_low,bb_width,
                    mom,roc,slope,
                    ctx,
                    plus_di,minus_di,adx
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, data)

        # purge
        cur_b.execute(f"""
            DELETE FROM {table_feat}
            WHERE ts NOT IN (
                SELECT ts FROM {table_feat}
                ORDER BY ts DESC LIMIT {keep}
            )
        """)

    con_b.commit()
    con_b.close()
    con_ob.close()
    log.info("[FULL] OK")

# =====================================================================================
# INCREMENTAL MODE
# =====================================================================================

def run_incr():
    log.info("[INCR] start")
    con_ob=conn(DB_OB)
    con_b =conn(DB_B)
    cur_b=con_b.cursor()

    cfg=[
        ("ohlcv_1m","feat_1m"),
        ("ohlcv_3m","feat_3m"),
        ("ohlcv_5m","feat_5m"),
    ]

    for table_ob, table_feat in cfg:
        last_ts=cur_b.execute(f"SELECT MAX(ts) FROM {table_feat}").fetchone()[0]
        if last_ts is None:
            log.warning(f"[INCR] {table_feat} vide → FULL")
            con_b.close()
            con_ob.close()
            return False

        new=con_ob.execute(f"""
            SELECT instId, ts, o,h,l,c,v
            FROM {table_ob}
            WHERE ts > ?
            ORDER BY instId, ts
        """,(last_ts,)).fetchall()

        if not new:
            log.info(f"[INCR] {table_feat} aucune nouvelle bougie")
            continue

        insts={}
        for instId,ts,o,h,l,c,v in new:
            insts.setdefault(instId,{"ts":[],"o":[],"h":[],"l":[],"c":[],"v":[]})
            insts[instId]["ts"].append(ts)
            insts[instId]["o"].append(o)
            insts[instId]["h"].append(h)
            insts[instId]["l"].append(l)
            insts[instId]["c"].append(c)
            insts[instId]["v"].append(v)

        for instId,dd in insts.items():
            feat=build_features(dd["ts"],dd["o"],dd["h"],dd["l"],dd["c"],dd["v"])
            data=[(instId,)+x for x in feat]

            cur_b.executemany(f"""
                INSERT OR REPLACE INTO {table_feat}(
                    instId, ts, o,h,l,c,v,
                    ema9,ema12,ema21,ema26,ema50,
                    macd,macdsignal,macdhist,
                    rsi,atr,
                    bb_mid,bb_std,bb_up,bb_low,bb_width,
                    mom,roc,slope,
                    ctx,
                    plus_di,minus_di,adx
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, data)

    con_b.commit()
    con_b.close()
    con_ob.close()
    log.info("[INCR] OK")
    return True

# =====================================================================================
# MAIN
# =====================================================================================

def main():
    t0=time.time()
    log.info("===== B_FEAT START =====")

    con_ob=conn(DB_OB)

    checks=[
        ("ohlcv_1m",60,120,1500),
        ("ohlcv_3m",180,300,500),
        ("ohlcv_5m",300,300,500),
    ]

    for table, tf_sec, max_age, max_rows in checks:
        ok,reason=check_ob(con_ob,table,tf_sec,max_age,max_rows)
        if not ok:
            log.warning(f"[CHECK] {table} KO → {reason} → FULL")
            con_ob.close()
            run_full()
            log.info(f"===== B_FEAT END (FULL) {time.time()-t0:.3f}s =====")
            return

    con_ob.close()

    # try incremental
    if not run_incr():
        log.warning("[MAIN] incr KO → FULL")
        run_full()
        log.info(f"===== B_FEAT END (FULL) {time.time()-t0:.3f}s =====")
        return

    log.info(f"===== B_FEAT END (INCR) {time.time()-t0:.3f}s =====")

if __name__=="__main__":
    main()

