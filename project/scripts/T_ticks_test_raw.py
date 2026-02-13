#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio, json, time, websockets

WS_URL = "wss://ws.bitget.com/v2/ws/public"
INSTRUMENTS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

async def test():
    async with websockets.connect(WS_URL, ping_interval=None) as ws:
        subs = [{"instType": "USDT-FUTURES", "channel": "ticker", "instId": i} for i in INSTRUMENTS]
        msg = {"op": "subscribe", "args": subs}
        await ws.send(json.dumps(msg))
        print("✅ Sent:", msg)

        async def pinger():
            while True:
                await asyncio.sleep(10)
                await ws.send('{"op":"ping"}')
        asyncio.create_task(pinger())

        while True:
            raw = await ws.recv()
            ts = time.strftime("%H:%M:%S")
            print(f"\n[{ts}] RAW →", raw[:250])

            try:
                data = json.loads(raw)
                if "data" in data:
                    for d in data["data"]:
                        inst = d.get("instId")
                        pr   = d.get("lastPr")
                        if inst and pr:
                            print(f"→ Parsed {inst} = {pr}")
            except Exception as e:
                print("⚠️ Parse error:", e)

asyncio.run(test())

