# scalper/backtest/market_data.py
from __future__ import annotations

import json, time
from dataclasses import dataclass
from typing import List, Tuple, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import pandas as pd

# Timeframe -> param API
# ⚠️ MIX utilise 'granularity' avec '5min', '1h', '1day', etc.
_GRAN_MIX = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day",
}
# ⚠️ SPOT utilise 'period' avec '5min', '1hour', etc.
_PERIOD_SPOT = {
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day",
}

@dataclass
class BitgetConfig:
    market: str = "mix"   # 'mix' (USDT-M perp) ou 'spot'
    timeout: int = 20
    max_retries: int = 3
    base_spot_candles: str = "https://api.bitget.com/api/spot/v1/market/candles"
    base_mix_candles:  str = "https://api.bitget.com/api/mix/v1/market/candles"

def _http_get(url: str, timeout: int) -> dict:
    req = Request(url, headers={"User-Agent": "scalper-backtest/1.2"})
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
    Télécharge OHLCV Bitget (public, sans auth).
    mix : /api/mix/v1/market/candles?symbol=BTCUSDT_UMCBL&granularity=5min&limit=...
    spot: /api/spot/v1/market/candles?symbol=BTCUSDT_SPBL&period=5min&limit=...
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

    last_err: Optional[Exception] = None
    for attempt in range(cfg.max_retries + 1):
        try:
            data = _http_get(url, cfg.timeout)
            # Bitget peut renvoyer {code,msg,data} ou une liste brute
            if isinstance(data, dict):
                # si code non 00000 on remonte l’erreur lisible
                code = data.get("code")
                if code and str(code) != "00000" and "data" not in data:
                    raise RuntimeError(f"Bitget error {code}: {data.get('msg')}")
                rows = data.get("data", [])
            else:
                rows = data

            if not isinstance(rows, list):
                raise ValueError(f"Réponse inattendue: {data}")

            # Format: [ts, open, high, low, close, volume, ...] (ts ms, strings)
            recs: List[Tuple[int, float, float, float, float, float]] = []
            for r in rows:
                ts = int(str(r[0]))
                o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
                recs.append((ts, o, h, l, c, v))
            recs.sort(key=lambda x: x[0])

            df = pd.DataFrame(recs, columns=["ts", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            return df.drop(columns=["ts"]).set_index("timestamp")

        except (URLError, HTTPError, ValueError, KeyError, RuntimeError) as e:
            last_err = e
            time.sleep(min(2 ** attempt, 5))

    raise RuntimeError(f"Bitget OHLCV fetch failed for {symbol} {timeframe}: {last_err}")