from __future__ import annotations
import os, time, logging
from datetime import datetime, timezone
from engine.adapters.bitget.client import BitgetClient

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)

def main() -> None:
    symbol  = os.getenv("LIVE_SYMBOL",  "BTCUSDT").upper()
    tf      = os.getenv("LIVE_TF",      "1m")
    market  = os.getenv("LIVE_MARKET",  "umcbl")  # unified-margin coin futures
    warmup  = int(os.getenv("WARMUP", "200"))
    poll    = float(os.getenv("POLL_SEC", "2.0"))

    log = logging.getLogger("ticker_logger")
    log.info("live start  symbol=%s  tf=%s  market=%s", symbol, tf, market)

    c = BitgetClient(market=market)

    rows = c.fetch_ohlcv(symbol, tf, limit=warmup)
    if not rows:
        log.error("no warmup data; abort")
        return
    last_ts = rows[-1][0]
    last_close = float(rows[-1][4])
    log.info("warmup loaded rows=%d last_close=%.4f", len(rows), last_close)

    while True:
        try:
            latest = c.fetch_ohlcv(symbol, tf, limit=2)
            if latest and latest[-1][0] != last_ts:
                last_ts = latest[-1][0]
                last_close = float(latest[-1][4])
                ts = datetime.fromtimestamp(last_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")
                log.info("NEW_CANDLE ts=%s close=%.4f", ts, last_close)
        except Exception as e:
            log.exception("loop error: %s", e)
        time.sleep(poll)

if __name__ == "__main__":
    main()
