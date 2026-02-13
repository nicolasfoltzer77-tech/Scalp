#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio, json, websockets, datetime, re

WS_URL = "wss://ws.bitget.com/mix/v1/stream"

# liste restreinte pour test
INSTRUMENTS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

async def listen():
    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        subs = []
        for inst in INSTRUMENTS:
            subs.append({
                "op": "subscribe",
                "args": [f"ticker:{inst}_UMCBL"]
            })
        for s in subs:
            await ws.send(json.dumps(s))
        print("Subscriptions sent:", subs)

        count = 0
        while True:
            msg = await ws.recv()
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"\n[{ts}] RAW:", msg[:200])  # tronqué si long

            # test parsing brut
            try:
                clean = re.search(r'\{.*\}', msg)
                obj = json.loads(clean.group(0)) if clean else None
                if obj:
                    ticker = obj.get("data", [{}])[0]
                    inst = ticker.get("symbol", "?")
                    last = ticker.get("last", "?")
                    print(f"→ Parsed {inst} = {last}")
            except Exception as e:
                print("⚠️ Parse error:", e)

            count += 1
            if count >= 5:
                break

asyncio.run(listen())

