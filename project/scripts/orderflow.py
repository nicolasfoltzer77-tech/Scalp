#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3, json, time, threading, logging, traceback
import websocket

ROOT = "/opt/scalp/project"
DB_G = f"{ROOT}/data/gest.db"
DB_OF = f"{ROOT}/data/orderflow.db"

LOG = f"{ROOT}/logs/orderflow.log"
logging.basicConfig(
    filename=LOG,
    level=logging.DEBUG,
    format="%(asctime)s ORDERFLOW %(levelname)s %(message)s"
)
log = logging.getLogger("ORDERFLOW")


# ============================================================
# DB UTILS
# ============================================================
def conn(path):
    c = sqlite3.connect(path, timeout=3, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA busy_timeout=3000;")
    return c


# ============================================================
# READ ACTIVE COINS FROM gest
# ============================================================
def load_active_coins():
    try:
        c = conn(DB_G)
        rows = c.execute("SELECT instId FROM v_active_coins;").fetchall()
        coins = set()

        for (instId,) in rows:
            if instId:
                inst = instId.replace("/", "")  # normalize
                coins.add(inst)

        log.info(f"[ACTIVE] {coins}")
        return coins
    except Exception as e:
        log.error(f"[ERR] load_active_coins {e}")
        return set()


# ============================================================
# ORDERFLOW CLIENT
# ============================================================
BITGET_WS = "wss://ws.bitget.com/v2/ws/public"


class OrderFlowClient:
    def __init__(self):
        self.ws = None
        self.active = load_active_coins()
        self.last_refresh = time.time()
        self.subscribed = False

    # -----------------------------------------
    # WS CALLBACK : open
    # -----------------------------------------
    def on_open(self, ws):
        log.info("WS OPEN")

        # subscribe immediately
        self.subscribe_all()
        self.subscribed = True

    # -----------------------------------------
    # WS CALLBACK : message
    # -----------------------------------------
    def on_message(self, ws, msg):
        try:
            data = json.loads(msg)

            # ignore subscription confirmations
            if "event" in data:
                return

            if "data" not in data:
                return

            arg = data.get("arg", {})
            instId = arg.get("instId")
            if not instId:
                return

            inst = instId.replace("/", "")
            snapshot = data["data"][0]

            best_bid = None
            best_ask = None
            bid_size = None
            ask_size = None

            bids = snapshot.get("bids", [])
            asks = snapshot.get("asks", [])

            if bids:
                best_bid = float(bids[0][0])
                bid_size = float(bids[0][1])

            if asks:
                best_ask = float(asks[0][0])
                ask_size = float(asks[0][1])

            ts = int(snapshot["ts"])

            # save into DB
            c = conn(DB_OF)
            c.execute("""
                REPLACE INTO books1(instId, ts_ms, best_bid, best_ask, bid_size, ask_size)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (inst, ts, best_bid, best_ask, bid_size, ask_size))
            c.commit()

        except Exception as e:
            log.error(f"[ERR] on_message {e} {traceback.format_exc()}")

    # -----------------------------------------
    # WS CALLBACK : error
    # -----------------------------------------
    def on_error(self, ws, err):
        log.error(f"WS ERROR {err}")

    # -----------------------------------------
    # WS CALLBACK : close
    # -----------------------------------------
    def on_close(self, ws, *args):
        log.warning("WS CLOSED")

    # -----------------------------------------
    # SUBSCRIBE ALL ACTIVE COINS
    # -----------------------------------------
    def subscribe_all(self):
        if not self.active:
            log.warning("[SUB] No active coins to subscribe")
            return

        for inst in self.active:
            req = {
                "op": "subscribe",
                "args": [{
                    "instType": "USDT-FUTURES",
                    "channel": "books1",
                    "instId": inst,
                    "debounce": "true"
                }]
            }

            try:
                self.ws.send(json.dumps(req))
                log.info(f"[SUB] {inst}")
            except Exception as e:
                log.error(f"[ERR] subscribe {inst} {e}")

    # -----------------------------------------
    # MAIN LOOP
    # -----------------------------------------
    def run(self):
        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    BITGET_WS,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )

                log.info(f"Connecting to {BITGET_WS}")

                # blocking call
                self.ws.run_forever(ping_interval=20, ping_timeout=10)

            except Exception as e:
                log.error(f"[ERR] run loop {e}")

            time.sleep(2)  # reconnect delay


# ============================================================
# MAIN
# ============================================================
def main():
    client = OrderFlowClient()
    client.run()


if __name__ == "__main__":
    main()

