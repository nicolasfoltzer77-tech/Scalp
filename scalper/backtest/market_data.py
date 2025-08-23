# scalper/backtest/market_data.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd


# Timeframe -> param API
_GRAN_MIX = {  # mix (futures) uses 'granularity'
    "1m": "1min", "3m": "3min", "5m": "5m", "15m": "15m",
    "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1day",
}
_PERIOD_SPOT = {  # spot uses 'period'
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day",
}

@dataclass
class BitgetConfig:
    market: str = "mix"   # "mix" (USDT‑M futures perp) ou "spot"
    timeout: int = 20
    max_retries: int = 3
    # v1 endpoints stables (OK pour data publiques)
    base_spot_candles: str = "https://api.bitget.com/api/spot/v1/market/candles"
    base_mix_candles: str  = "https://api.bitget.com/api/mix/v1/market/candles"

def _http_get(url: str, timeout: int) -> dict:
    req = Request(url, headers={"User-Agent": "scalper-backtest/1.1"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))

def _mix_symbol(sym: str) -> str:
    sym = sym.upper()
    return f"{sym}_UMCBL" if not sym.endswith("_UMCBL") else sym

def _spot_symbol(sym: str) -> str:
    sym = sym.upper()
    return f"{sym}_SPBL" if not sym.endswith("_SPBL") else sym

def fetch_ohlcv_bitget(
    symbol: str,
    timeframe: str,
    *,
    limit: int = 1000,
    cfg: Optional[BitgetConfig] = None,
) -> pd.DataFrame:
    """
    Télécharge des bougies OHLCV auprès de l'API publique de Bitget (sans auth).

    - market='mix'  → GET /api/mix/v1/market/candles?symbol=BTCUSDT_UMCBL&granularity=5m&limit=...
    - market='spot' → GET /api/spot/v1/market/candles?symbol=BTCUSDT_SPBL&period=5min&limit=...

    Retour: DataFrame index=timestamp UTC, colonnes: open, high, low, close, volume
    """
    cfg = cfg or BitgetConfig()
    market = cfg.market.lower().strip()
    tf = timeframe.lower().strip()

    if market == "mix":
        if tf not in _GRAN_MIX:
            raise ValueError(f"Timeframe non supporté pour mix: {tf}")
        sym = _mix_symbol(symbol)
        gran = _GRAN_MIX[tf]
        url = f"{cfg.base_mix_candles}?symbol={sym}&granularity={gran}&limit={int(limit)}"
    elif market == "spot":
        if tf not in _PERIOD_SPOT:
            raise ValueError(f"Timeframe non supporté pour spot: {tf}")
        sym = _spot_symbol(symbol)
        per = _PERIOD_SPOT[tf]
        url = f"{cfg.base_spot_candles}?symbol={sym}&period={per}&limit={int(limit)}"
    else:
        raise ValueError(f"market inconnu: {cfg.market} (attendu 'mix' ou 'spot')")

    err: Optional[Exception] = None
    for attempt in range(cfg.max_retries + 1):
        try:
            data = _http_get(url, cfg.timeout)
            # v1 spot/mix peuvent renvoyer soit une liste brute, soit { "data": [...] }
            rows = data.get("data") if isinstance(data, dict) else data
            if not isinstance(rows, list):
                raise ValueError(f"Réponse inattendue: {data}")

            # Format: [ts, open, high, low, close, volume, ...] (ts en ms, strings)
            records: List[Tuple[int, float, float, float, float, float]] = []
            for r in rows:
                ts = int(str(r[0]))
                o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
                records.append((ts, o, h, l, c, v))

            records.sort(key=lambda x: x[0])
            df = pd.DataFrame(records, columns=["ts", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            df = df.drop(columns=["ts"]).set_index("timestamp")
            return df

        except (URLError, HTTPError, ValueError, KeyError) as e:
            err = e
            time.sleep(min(2 ** attempt, 5))

    raise RuntimeError(f"Bitget OHLCV fetch failed for {symbol} {timeframe}: {err}")