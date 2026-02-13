#!/usr/bin/env python3
import sqlite3, math, time

DB_A = "/opt/scalp/project/data/a.db"
DB_U = "/opt/scalp/project/data/universe.db"
DB_OB = "/opt/scalp/project/data/ob.db"
TF = "5m"

def softmax(x):
    e = [math.exp(i) for i in x]
    s = sum(e)
    return [v/s for v in e]

def get_universe():
    con = sqlite3.connect(DB_U)
    rows = con.execute("SELECT instId FROM v_universe_tradable ORDER BY instId").fetchall()
    con.close()
    return [r[0] for r in rows]

def load_ob(inst):
    con = sqlite3.connect(DB_OB)
    row = con.execute(f"SELECT rsi FROM ob_{TF} WHERE instId=? ORDER BY ts DESC LIMIT 1", (inst,)).fetchone()
    con.close()
    return row[0] if row else None

def compute_ctx(rsi):
    if rsi < 30: return "bullish"
    if rsi > 70: return "bearish"
    if 45 <= rsi <= 55: return "range"
    return "none"

def compute_score_A(ctx):
    if ctx == "bullish": return 0.8
    if ctx == "bearish": return -0.8
    if ctx == "range": return 0.0
    return 0.0

def run():
    insts = get_universe()
    now = int(time.time()*1000)
    out = []

    for inst in insts:
        rsi = load_ob(inst)
        if rsi is None:
            continue
        ctx = compute_ctx(rsi)
        score_A = compute_score_A(ctx)
        p_buy, p_sell = softmax([score_A, -score_A])
        out.append((inst, now, 0.0, score_A, p_buy, p_sell, ctx))

    con = sqlite3.connect(DB_A)
    con.execute("DELETE FROM ctx_a_latest")
    con.executemany("INSERT INTO ctx_a_latest(instId,ts,score_U,score_A,p_buy,p_sell,ctx) VALUES (?,?,?,?,?,?,?)", out)
    con.commit()
    con.close()

if __name__ == "__main__":
    run()

