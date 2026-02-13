#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import sqlite3
import time
import websockets

ROOT = "/opt/scalp/project"
DB_TICKS = f"{ROOT}/data/t.db"
DB_UNIVERSE = f"{ROOT}/data/universe.db"
LOG = f"{ROOT}/logs/ticks.log"

# ✅ BON ENDPOINT WS BITGET (V2)
WS_URL = "wss://ws.bitget.com/v2/ws/public"

logging.basicConfig(
    filename=LOG,
    level=logging.INFO,
    format="%(asctime)s TICKS %(levelname)s %(message)s"
)
log = logging.getLogger("TICKS")

def conn(path):
    c = sqlite3.connect(path, timeout=30, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA busy_timeout=5000;")
    return c

def load_universe():
    cu = conn(DB_UNIVERSE)
    rows = cu.execute("SELECT instId FROM v_universe_tradable").fetchall()
    return [r[0] for r in rows]

def canon(inst):
    return inst.replace("/", "")

async def run():
    insts = load_universe()
    if not insts:
        log.error("Universe vide")
        return

    args = [{
        "instType": "USDT-FUTURES",
        "channel": "ticker",
        "instId": canon(inst)
    } for inst in insts]

    sub = {"op": "subscribe", "args": args}

    log.info(f"WS connect, subscribing {len(args)} symbols")

    async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=10) as ws:
        await ws.send(json.dumps(sub))
        log.info("SUBSCRIBE SENT")

        c = conn(DB_TICKS)

        async for msg in ws:
            data = json.loads(msg)

            if "data" not in data:
                continue

            for d in data["data"]:
                inst_raw = d.get("instId")
                last = float(d.get("lastPr"))
                ts = int(d.get("ts"))

                inst = inst_raw.replace("USDT", "/USDT")

                c.execute(
                    "INSERT INTO ticks(instId, instId_s, lastPr, ts_ms) VALUES (?,?,?,?)",
                    (inst, inst, last, ts)
                )

def main():
    log.info("START TICKS WS")
    while True:
        try:
            asyncio.run(run())
        except Exception as e:
            log.error(f"WS error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()

