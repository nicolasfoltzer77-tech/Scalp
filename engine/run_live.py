from __future__ import annotations
import os
import time
import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from engine.adapters.bitget.client import BitgetClient

# ---------- config ----------
SYMBOL = os.getenv("LIVE_SYMBOL", "BTCUSDT")
TF     = os.getenv("LIVE_TF", "1m")
MARKET = os.getenv("LIVE_MARKET", "umcbl")   # coin-margined unified futures
LIMIT  = int(os.getenv("LIVE_WARMUP", "200"))
POLL_S = float(os.getenv("LIVE_POLL_SECONDS", "3"))
DRY    = os.getenv("DRY_RUN", "true").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)

COLS = ["timestamp","open","high","low","close","volume","quote_volume"]

def ts_ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)

def main() -> None:
    log = logging.getLogger("run_live")
    log.info("live start  symbol=%s tf=%s market=%s dry_run=%s",
             SYMBOL, TF, MARKET, DRY)

    c = BitgetClient(market=MARKET)

    # --- warmup ---
    rows: List[List[str]] = c.fetch_ohlcv(SYMBOL, TF, limit=LIMIT)
    if not rows:
        raise RuntimeError("warmup returned no data")

    # normalise -> DataFrame
    df = pd.DataFrame(rows, columns=COLS)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype("int64"), unit="ms", utc=True)
    df[["open","high","low","close","volume","quote_volume"]] = df[
        ["open","high","low","close","volume","quote_volume"]
    ].astype("float64")

    last_ts = int(rows[-1][0])
    last_close = float(rows[-1][4])
    log.info("warmup loaded rows=%d last_close=%.4f", len(df), last_close)

    # --- live loop ---
    while True:
        try:
            time.sleep(POLL_S)
            r = c.fetch_ohlcv(SYMBOL, TF, limit=1)
            if not r:
                continue

            ts, o, h, l, cl, v, qv = r[0]
            ts = int(ts)

            if ts <= last_ts:
                # pas encore de nouvelle bougie
                continue

            # *** IMPORTANT *** : ne plus utiliser df.append !
            # Ajout robuste d'une ligne
            df.loc[len(df)] = [
                pd.to_datetime(ts, unit="ms", utc=True),
                float(o), float(h), float(l), float(cl),
                float(v), float(qv)
            ]

            last_ts = ts
            last_close = float(cl)
            log.info("NEW_CANDLE ts=%s close=%.4f",
                     ts_ms_to_dt(ts).strftime("%Y-%m-%d %H:%M:%S%z"),
                     last_close)

            # Ici tu déclenches tes signaux/ordres si besoin…

        except Exception as e:
            log.exception("loop error: %s", e)
            time.sleep(2)

if __name__ == "__main__":
    main()
