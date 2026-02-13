#!/usr/bin/env python3
import asyncio
import json
import websockets
import sqlite3
import time

WS_URL = "wss://ws.bitget.com/v2/ws/public"
DB_U = "/opt/scalp/project/data/universe.db"

# Timeframes in ms for identifying CLOSED candles
TF = {
    "candle5m":  5 * 60 * 1000,
    "candle15m": 15 * 60 * 1000,
    "candle30m": 30 * 60 * 1000
}

################################################################
# Load universe from u.db
################################################################
def load_universe():
    conn = sqlite3.connect(DB_U)
    rows = conn.execute("SELECT instId FROM v_universe_tradable ORDER BY instId;").fetchall()
    conn.close()
    return [r[0] for r in rows]


################################################################
# Build subscription message
################################################################
def build_sub(universe):
    args = []
    for inst in universe:
        args.append({"instType":"USDT-FUTURES","channel":"candle5m","instId":inst})
        args.append({"instType":"USDT-FUTURES","channel":"candle15m","instId":inst})
        args.append({"instType":"USDT-FUTURES","channel":"candle30m","instId":inst})
    return {"op":"subscribe","args":args}


################################################################
# Core WS loop
################################################################
async def ws_loop():
    universe = load_universe()
    sub = build_sub(universe)

    while True:
        try:
            print("[WS] Connecting...")
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                print("[WS] Connected, subscribing…")
                await ws.send(json.dumps(sub))

                while True:
                    raw = await ws.recv()
                    data = json.loads(raw)

                    # Ignore heartbeats
                    if isinstance(data, dict) and data.get("event") in ("ping","pong"):
                        continue

                    # Only candle messages
                    if "arg" not in data or "data" not in data:
                        continue

                    channel = data["arg"].get("channel")
                    inst    = data["arg"].get("instId")
                    rows    = data["data"]

                    if channel not in TF:
                        continue

                    tf_ms = TF[channel]

                    # Process each kline
                    for k in rows:
                        ts     = int(k[0])
                        open_  = float(k[1])
                        high   = float(k[2])
                        low    = float(k[3])
                        close  = float(k[4])
                        volume = float(k[5])

                        # === FILTER: closed candles only ===
                        if ts % tf_ms != 0:
                            continue

                        print(f"[{channel}] CLOSED {inst}  ts={ts}  "
                              f"open={open_} high={high} low={low} "
                              f"close={close} vol={volume}")

        except Exception as e:
            print(f"[WS] Error: {e}, retry in 5s…")
            await asyncio.sleep(5)


################################################################
# Entry point
################################################################
if __name__ == "__main__":
    asyncio.run(ws_loop())

