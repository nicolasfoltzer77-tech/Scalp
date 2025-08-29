from __future__ import annotations
import os
import time
import logging
from typing import Dict, Any, List

import pandas as pd

from engine.adapters.bitget import BitgetClient
from engine.utils.pdtools import df_from_ohlcv, df_add_row

# ------------ Config basique (env + valeurs par défaut) -----------------
SYMBOL   = os.getenv("LIVE_SYMBOL", "BTCUSDT")
TF       = os.getenv("LIVE_TF", "1m")             # ex: "1m", "5m"
MARKET   = os.getenv("LIVE_MARKET", "umcbl")      # futures/UMCBL
DRY_RUN  = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")
MAX_ROWS = int(os.getenv("LIVE_MAX_ROWS", "10000"))
WARMUP   = int(os.getenv("LIVE_WARMUP", "200"))   # nb bougies de préchauffe

# ------------ Logging sobre (systemd récupère stdout) -------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("scalp-live")

# ------------ Outils ----------------------------------------------------
TF_TO_SEC = {"1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600}

def tf_seconds(tf: str) -> int:
    return TF_TO_SEC.get(tf, 60)

# ------------ Boucle principale ----------------------------------------
def main() -> None:
    client = BitgetClient(market=MARKET)
    log.info("live start  symbol=%s tf=%s market=%s dry_run=%s", SYMBOL, TF, MARKET, DRY_RUN)

    # 1) Warmup
    rows = client.fetch_ohlcv(SYMBOL, TF, limit=WARMUP)
    df = df_from_ohlcv(rows)
    if df.empty:
        raise RuntimeError("Warmup OHLCV vide")

    last_close = float(df.iloc[-1]["close"])
    log.info("warmup loaded rows=%s last_close=%.4f", len(df), last_close)

    # 2) Boucle
    period = tf_seconds(TF)
    next_poll = time.time()
    while True:
        try:
            # on poll léger: on ne prend que les 2 dernières pour détecter changement
            tail_rows = client.fetch_ohlcv(SYMBOL, TF, limit=2)
            tail_df = df_from_ohlcv(tail_rows)
            if not tail_df.empty:
                latest: Dict[str, Any] = tail_df.iloc[-1].to_dict()

                # Si on a déjà cette timestamp, on UPDATE la dernière ligne ; sinon on APPEND
                if not df.empty and "timestamp" in df.columns and latest.get("timestamp") == df.iloc[-1]["timestamp"]:
                    # update last row en place
                    for k, v in latest.items():
                        df.at[df.index[-1], k] = v
                else:
                    df = df_add_row(df, latest, max_rows=MAX_ROWS)

                # Exemple: simple log (et endroit pour générer un signal)
                log.debug("last close=%.4f size=%d", float(df.iloc[-1]["close"]), len(df))
        except Exception as e:
            log.error("live loop error: %s", e, exc_info=True)

        # cadence = toutes les 3 sec pour 1m (peut être ajusté)
        next_poll += max(3, period // 20)
        sleep_s = max(1, int(next_poll - time.time()))
        time.sleep(sleep_s)

if __name__ == "__main__":
    main()
