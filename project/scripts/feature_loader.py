import sqlite3, time

DB_T = "/opt/scalp/project/data/t.db"
DB_OF = "/opt/scalp/project/data/orderflow.db"
DB_CTX = "/opt/scalp/project/data/ctx.db"

def load_features():
    return {
        "price": load_price(),
        "atr": load_atr(),
        "of": load_orderflow(),
        "ctx": load_ctx()
    }

def load_price():
    c = sqlite3.connect(DB_T)
    rows = c.execute("""
        SELECT instId, ts, price
        FROM ticks
        WHERE ts > ?
    """, (int(time.time()*1000)-5000,)).fetchall()
    data = {}
    for inst, ts, px in rows:
        data.setdefault(inst, []).append((ts, px))
    return data

def load_atr():
    c = sqlite3.connect(DB_T)
    rows = c.execute("""
        SELECT instId, ts, atr
        FROM atr
        WHERE ts > ?
    """, (int(time.time()*1000)-60000,)).fetchall()
    data = {}
    for inst, ts, v in rows:
        data.setdefault(inst, []).append((ts, v))
    return data

def load_orderflow():
    c = sqlite3.connect(DB_OF)
    rows = c.execute("""
        SELECT instId, ts_ms, best_bid, best_ask, bid_size, ask_size
        FROM books1
        WHERE ts_ms > ?
    """, (int(time.time()*1000)-5000,)).fetchall()
    data = {}
    for inst, ts, bb, ba, bs, asz in rows:
        data.setdefault(inst, []).append((ts, bb, ba, bs, asz))
    return data

def load_ctx():
    c = sqlite3.connect(DB_CTX)
    rows = c.execute("""
        SELECT instId, ctx, score_final
        FROM v_ctx_latest
    """).fetchall()
    return {r[0]: {"ctx": r[1], "score_C": r[2]} for r in rows}

