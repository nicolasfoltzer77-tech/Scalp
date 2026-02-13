#!/usr/bin/env python3
import asyncio
import json
import sqlite3
import websockets
import time
from datetime import datetime

WS_URL = "wss://ws.bitget.com/v2/ws/public"

DB_WS = "/opt/scalp/project/data/ws.db"
DB_U  = "/opt/scalp/project/data/universe.db"

TF = {
    "candle5m":  5  * 60 * 1000,
    "candle15m": 15 * 60 * 1000,
    "candle30m": 30 * 60 * 1000
}

###############################################################################
# DB Helpers
###############################################################################
def load_universe():
    conn = sqlite3.connect(DB_U)
    rows = conn.execute("SELECT instId FROM v_universe_tradable ORDER BY instId;").fetchall()
    conn.close()
    return [r[0] for r in rows]

def wsdb_conn():
    conn = sqlite3.connect(DB_WS, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

###############################################################################
# WS Subscription builder
###############################################################################
def build_sub(universe):
    args = []
    for instId in universe:
        args.append({"instType":"USDT-FUTURES","channel":"candle5m","instId":instId})
        args.append({"instType":"USDT-FUTURES","channel":"candle15m","instId":instId})
        args.append({"instType":"USDT-FUTURES","channel":"candle30m","instId":instId})
    return {"op":"subscribe", "args":args}

###############################################################################
# Insert into WS DB (closed candles only)
###############################################################################
def insert_ws_candle(conn, table, instId, ts, o, h, l, c, v):
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {table}(instId, ts, open, high, low, close, volume)
        VALUES (?,?,?,?,?,?,?)
        """,
        (instId, ts, o, h, l, c, v)
    )

###############################################################################
# Main WebSocket loop
###############################################################################
async def run_ws():
    universe = load_universe()
    sub = build_sub(universe)

    ws_conn = wsdb_conn()

    while True:
        try:
            print("[WS] Connecting...")
            async with websockets.connect(
                WS_URL,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=1
            ) as ws:

                print("[WS] Connected, subscribing…")
                await ws.send(json.dumps(sub))

                async def keep_alive():
                    while True:
                        await asyncio.sleep(15)
                        try:
                            await ws.send(json.dumps({"event":"ping"}))
                        except:
                            break

                asyncio.create_task(keep_alive())

                while True:
                    raw = await ws.recv()
                    data = json.loads(raw)

                    # Skip ping/pong
                    if isinstance(data, dict) and data.get("event") in ("ping","pong"):
                        continue

                    if "arg" not in data or "data" not in data:
                        continue

                    channel = data["arg"]["channel"]
                    instId  = data["arg"]["instId"]
                    rows    = data["data"]

                    if channel not in TF:
                        continue

                    tf_ms = TF[channel]
                    table = f"ws_ohlcv_{channel.replace('candle','')}"  # candle5m -> ws_ohlcv_5m

                    for k in rows:
                        ts = int(k[0])

                        # Only take closed candles
                        if ts % tf_ms != 0:
                            continue

                        o = float(k[1])
                        h = float(k[2])
                        l = float(k[3])
                        c = float(k[4])
                        v = float(k[5])

                        insert_ws_candle(ws_conn, table, instId, ts, o, h, l, c, v)

                        print(
                            f"[WS] CLOSED {channel} {instId} "
                            f"ts={ts} o={o} h={h} l={l} c={c} v={v}"
                        )

        except Exception as e:
            print(f"[WS] Error: {e}, retry in 5s…")
            await asyncio.sleep(5)

###############################################################################
# Entrypoint
###############################################################################
if __name__ == "__main__":
    asyncio.run(run_ws())

