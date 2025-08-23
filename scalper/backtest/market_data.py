# scalper/backtest/market_data.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd


# Map timeframe -> param Bitget `granularity`
_GRANULARITY = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
}

@dataclass
class BitgetConfig:
    market: str = "mix"   # "mix" (futures/USDT-M) ou "spot"
    timeout: int = 20
    max_retries: int = 3
    base_spot: str = "https://api.bitget.com/api/spot/v1/market/candles"
    base_mix: str  = "https://api.bitget.com/api/mix/v1/market/candles"

def _http_get(url: str, timeout: int) -> dict:
    req = Request(url, headers={"User-Agent": "scalper-backtest/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))

def _endpoint(cfg: BitgetConfig) -> str:
    return cfg.base_mix if cfg.market.lower() == "mix" else cfg.base_spot

def _granularity(tf: str) -> str:
    tf = tf.strip().lower()
    if tf not in _GRANULARITY:
        raise ValueError(f"Timeframe non supporté pour Bitget: {tf}")
    return _GRANULARITY[tf]

def fetch_ohlcv_bitget(
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
    cfg: Optional[BitgetConfig] = None,
) -> pd.DataFrame:
    """
    Télécharge des bougies OHLCV auprès de l'API publique de Bitget (pas d'auth).
    - symbol ex: BTCUSDT
    - timeframe ex: 1m,5m,15m,1h,4h,1d
    - limit: nb max de bougies (Bitget <= 1000)
    Retour: DataFrame index datetime UTC, colonnes: open, high, low, close, volume
    """
    cfg = cfg or BitgetConfig()
    gran = _granularity(timeframe)
    url = f"{_endpoint(cfg)}?symbol={symbol}&granularity={gran}&limit={int(limit)}"

    err: Optional[Exception] = None
    for attempt in range(cfg.max_retries + 1):
        try:
            data = _http_get(url, cfg.timeout)
            # Bitget renvoie une liste de listes (ordre: plus récentes en premier)
            if isinstance(data, dict) and "data" in data:
                rows = data["data"]
            else:
                rows = data
            # Format attendu: [ts, open, high, low, close, volume, ...]
            records: List[Tuple[int, float, float, float, float, float]] = []
            for r in rows:
                # ts peut être ms (int/str), le reste en str
                ts = int(str(r[0]))
                # Bitget renvoie ms -> pandas to_datetime(ms, unit='ms')
                o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
                records.append((ts, o, h, l, c, v))
            # tri chronologique croissant
            records.sort(key=lambda x: x[0])
            df = pd.DataFrame(records, columns=["ts", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            df = df.drop(columns=["ts"]).set_index("timestamp")
            return df
        except (URLError, HTTPError, ValueError, KeyError) as e:
            err = e
            time.sleep(min(2 ** attempt, 5))

    # si on arrive ici -> échec
    raise RuntimeError(f"Bitget OHLCV fetch failed for {symbol} {timeframe}: {err}")