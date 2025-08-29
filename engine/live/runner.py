from __future__ import annotations
import os, time, logging, traceback
import pandas as pd
from datetime import datetime, timezone
from engine.adapters.bitget import BitgetClient
from engine.live.strategy import EMACross

SYMBOL   = os.getenv("LIVE_SYMBOL", "BTCUSDT")
TF       = os.getenv("LIVE_TF", "1m")
MARKET   = os.getenv("LIVE_MARKET", "umcbl")
DRY_RUN  = os.getenv("DRY_RUN", "true").lower() in ("1","true","yes","on")
SIZE     = float(os.getenv("POSITION_SIZE", "0.001"))  # qty in coin
SLEEP_S  = int(os.getenv("LOOP_SLEEP_SEC", "2"))       # poll cadence
WARMUP_N = int(os.getenv("WARMUP_ROWS", "200"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
log = logging.getLogger("live")

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def main():
    log.info("live start  symbol=%s tf=%s market=%s dry_run=%s",
             SYMBOL, TF, MARKET, DRY_RUN)
    c = BitgetClient(market=MARKET)

    # ---- warmup
    rows = c.fetch_ohlcv(SYMBOL, TF, limit=WARMUP_N)
    df = pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume","quote_volume"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce").astype(float)
    closes = df["close"].tolist()
    last_close = closes[-1] if closes else None
    log.info("warmup loaded rows=%d last_close=%.4f", len(closes), (last_close or 0))
    strat = EMACross(fast=9, slow=21)
    strat.on_warmup(df)

    in_position = False
    entry_price = None

    # ---- main loop
    while True:
        try:
            # Pull the latest one or two candles to keep up
            new = c.fetch_ohlcv(SYMBOL, TF, limit=2)
            # Always keep order: oldest -> newest
            for row in new:
                px = float(row[4])
                # if candle newer than last seen, append
                if not closes or row[0] > (rows[-1][0] if rows else 0):
                    closes.append(px)
                    if len(closes) > max(2000, WARMUP_N + 1000):
                        closes = closes[-(WARMUP_N+500):]  # trim memory
                    rows.append(row)

            signal = strat.on_tick(closes)
            if signal:
                log.info("signal=%s price=%.4f pos=%s", signal, closes[-1], in_position)

            if signal == "long" and not in_position:
                if DRY_RUN:
                    in_position, entry_price = True, closes[-1]
                    log.info("DRY-RUN BUY qty=%s at=%.4f", SIZE, entry_price)
                else:
                    oid = c.place_order(symbol=SYMBOL, side="open_long", size=SIZE)
                    in_position = True
                    entry_price = closes[-1]
                    log.info("LIVE BUY oid=%s qty=%s at≈%.4f", oid, SIZE, entry_price)

            elif signal == "close" and in_position:
                if DRY_RUN:
                    pnl = closes[-1] - (entry_price or closes[-1])
                    log.info("DRY-RUN CLOSE at=%.4f PnL=%.2f", closes[-1], pnl)
                    in_position, entry_price = False, None
                else:
                    oid = c.place_order(symbol=SYMBOL, side="close_long", size=SIZE)
                    log.info("LIVE CLOSE oid=%s at≈%.4f", oid, closes[-1])
                    in_position, entry_price = False, None

        except Exception as e:
            log.error("loop error: %s", e)
            log.debug("trace:\n%s", traceback.format_exc())
            time.sleep(3)

        time.sleep(SLEEP_S)

if __name__ == "__main__":
    main()
