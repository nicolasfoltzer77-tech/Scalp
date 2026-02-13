#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP — TICKS COLLECTOR v2 (LAST + BID/ASK + SPREAD)

- instId canon = BASE/USDT
- WS Bitget : ticker USDT-FUTURES
- lastPr, bidPr, askPr stockés
- spread_bps calculé LIVE
- UN SEUL WRITER
- WAL SAFE
- AUCUN calcul métier (ledger only)
"""

import asyncio
import websockets
import json
import sqlite3
import threading
import time
from queue import Queue

ROOT = "/opt/scalp/project"
DB_T = f"{ROOT}/data/t.db"
DB_A = f"{ROOT}/data/a.db"

WS_URL = "wss://ws.bitget.com/v2/ws/public"

QUEUE_MAX = 8000
FLUSH_DELAY = 0.25
ROLLING_LIMIT = 200
CHECKPOINT_EVERY = 5.0

q = Queue(maxsize=QUEUE_MAX)
stop_event = threading.Event()

# =========================================================
# DB
# =========================================================
def conn_t():
    c = sqlite3.connect(
        DB_T,
        timeout=5,
        check_same_thread=False,
        isolation_level=None
    )
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    c.execute("PRAGMA wal_autocheckpoint=0;")
    return c

# =========================================================
# instId helpers
# =========================================================
def ws_to_canon(ws_id: str) -> str:
    s = ws_id.upper().replace("/", "")
    if not s.endswith("USDT"):
        return None
    return f"{s[:-4]}/USDT"

def canon_to_ws(instId: str) -> str:
    return instId.replace("/", "")

# =========================================================
# Symbols
# =========================================================
def load_symbols():
    c = sqlite3.connect(DB_A)
    rows = c.execute("SELECT instId FROM v_ctx_latest").fetchall()
    c.close()
    return [canon_to_ws(r[0]) for r in rows]

# =========================================================
# Writer
# =========================================================
def writer():
    conn = conn_t()
    cur = conn.cursor()

    buf = []
    last_flush = time.time()
    last_checkpoint = time.time()

    print("[ticks] Writer started (LAST + BID/ASK + SPREAD).")

    while not stop_event.is_set():
        try:
            row = q.get(timeout=FLUSH_DELAY)
            buf.append(row)
        except:
            pass

        now = time.time()

        # -------- FLUSH --------
        if buf and (now - last_flush) >= FLUSH_DELAY:
            try:
                cur.executemany("""
                    INSERT INTO ticks(instId,lastPr,bidPr,askPr,spread_bps,ts_ms)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(instId) DO UPDATE SET
                        lastPr=excluded.lastPr,
                        bidPr=excluded.bidPr,
                        askPr=excluded.askPr,
                        spread_bps=excluded.spread_bps,
                        ts_ms=excluded.ts_ms;
                """, buf)

                cur.executemany("""
                    INSERT INTO ticks_hist(instId,lastPr,bidPr,askPr,spread_bps,ts_ms)
                    VALUES (?,?,?,?,?,?);
                """, buf)

                for instId, *_ in buf:
                    cur.execute("""
                        DELETE FROM ticks_hist
                        WHERE instId=?
                          AND id NOT IN (
                            SELECT id FROM ticks_hist
                            WHERE instId=?
                            ORDER BY ts_ms DESC
                            LIMIT ?
                          );
                    """, (instId, instId, ROLLING_LIMIT))

                conn.commit()

            except Exception as e:
                print("[ticks] DB error:", e)
                conn.rollback()

            buf.clear()
            last_flush = now

        # -------- CHECKPOINT --------
        if (now - last_checkpoint) >= CHECKPOINT_EVERY:
            try:
                cur.execute("PRAGMA wal_checkpoint(PASSIVE);")
            except:
                pass
            last_checkpoint = now

    conn.close()
    print("[ticks] Writer stopped.")

# =========================================================
# Websocket
# =========================================================
async def ws_one(ws_inst):
    canon = ws_to_canon(ws_inst)
    if not canon:
        return

    sub = {
        "op": "subscribe",
        "args": [{
            "instType": "USDT-FUTURES",
            "channel": "ticker",
            "instId": ws_inst
        }]
    }

    msg = json.dumps(sub)

    while not stop_event.is_set():
        try:
            async with websockets.connect(
                WS_URL,
                ping_interval=15,
                ping_timeout=15,
                max_size=2**20
            ) as ws:

                await ws.send(msg)
                print(f"[ticks] {canon} subscribed")

                async for raw in ws:
                    data = json.loads(raw)
                    if "data" not in data:
                        continue

                    d = data["data"][0]

                    try:
                        lastPr = float(d["lastPr"])
                        bidPr  = float(d.get("bidPr") or 0)
                        askPr  = float(d.get("askPr") or 0)
                        ts_ms  = int(d["ts"])
                    except:
                        continue

                    spread_bps = None
                    if bidPr > 0 and askPr > 0 and askPr > bidPr:
                        mid = (bidPr + askPr) / 2
                        spread_bps = (askPr - bidPr) / mid * 10_000

                    if not q.full():
                        q.put((canon, lastPr, bidPr, askPr, spread_bps, ts_ms))

        except Exception as e:
            print(f"[ticks] {canon} WS error:", e)
            await asyncio.sleep(1.0)

# =========================================================
# MAIN
# =========================================================
def main():
    syms = load_symbols()
    print(f"[ticks] Starting {len(syms)} instruments")

    wt = threading.Thread(target=writer, daemon=True)
    wt.start()

    try:
        asyncio.run(run_all(syms))
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        wt.join()

async def run_all(symbols):
    tasks = [asyncio.create_task(ws_one(s)) for s in symbols]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    main()

