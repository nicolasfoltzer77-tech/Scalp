# scalper/adapters/bitget_fetch.py
from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, Optional

BT_DEBUG = int(os.getenv("BT_DEBUG", "0") or "0")

def _log(msg: str) -> None:
    if BT_DEBUG:
        print(f"[bt.debug] {msg}", flush=True)

_TF_TO_SECS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}
_TF_TO_MIX = {  # granularity pour mix (docs Bitget)
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day",
}
_TF_TO_SPOT = {  # period pour spot (docs Bitget)
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1hour", "4h": "4hour", "1d": "1day",
}

def _await_if_needed(val: Any) -> Any:
    if inspect.isawaitable(val):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(val)
        else:
            fut = asyncio.run_coroutine_threadsafe(val, asyncio.get_running_loop())
            return fut.result()
    return val

class BitgetFetchAdapter:
    """
    Adaptateur qui fournit une méthode CCXT-like:
      fetch_ohlcv(symbol, timeframe='5m', since=None, limit=1000)
    au-dessus d'un client Bitget existant (sync ou async).
    """
    def __init__(self, client: Any, *, market_hint: str | None = None):
        self.client = client
        self.market_hint = (market_hint or "").lower() or None
        _log(f"BitgetFetchAdapter attaché sur {type(client).__name__} (market_hint={self.market_hint})")
        if hasattr(client, "fetch_ohlcv") and callable(getattr(client, "fetch_ohlcv")):
            _log("Client expose déjà fetch_ohlcv → adaptation inutile (utilisation directe).")

    @staticmethod
    def _possible_methods(client: Any) -> list[str]:
        names = dir(client)
        base = [
            "fetch_ohlcv",
            "get_candlesticks", "candlesticks", "get_candles", "candles",
            "klines", "get_klines", "kline",
            "mix_get_candles", "mix_candles",
            "spot_get_candles", "spot_candles",
            "market_candles", "public_candles",
        ]
        # + heuristique: tout ce qui contient candle/kline
        extra = [n for n in names if ("candle" in n.lower() or "kline" in n.lower()) and callable(getattr(client, n))]
        out = []
        for n in base + extra:
            if n in names and callable(getattr(client, n)) and n not in out:
                out.append(n)
        _log(f"Méthodes candidates détectées: {out or '(aucune)'}")
        return out

    @staticmethod
    def _sym_variants(sym: str) -> list[str]:
        s = sym.upper()
        out = [s]
        if not s.endswith("_UMCBL"):
            out.append(f"{s}_UMCBL")
        if not s.endswith("_SPBL"):
            out.append(f"{s}_SPBL")
        _log(f"Variantes symbole testées: {out}")
        return out

    @staticmethod
    def _param_variants(timeframe: str, market_hint: Optional[str]) -> list[dict]:
        secs = _TF_TO_SECS.get(timeframe, 300)
        mix = _TF_TO_MIX.get(timeframe, "5min")
        spot = _TF_TO_SPOT.get(timeframe, "5min")
        variants = []
        if market_hint == "mix":
            variants.append({"granularity": mix})
        if market_hint == "spot":
            variants.append({"period": spot})
        variants += [
            {"timeframe": timeframe},
            {"interval": timeframe},
            {"k": secs},
            {"granularity": mix},
            {"period": spot},
        ]
        _log(f"Variantes params testées pour tf={timeframe}: {variants}")
        return variants

    @staticmethod
    def _normalize_rows(raw: Any) -> list[list[float]]:
        import pandas as pd  # local import
        if raw is None:
            raise ValueError("OHLCV vide")
        if isinstance(raw, dict) and "data" in raw:
            raw = raw["data"]
        if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
            out = []
            for r in raw:
                ts = int(str(r[0]))
                o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
                out.append([ts, o, h, l, c, v])
            return out
        if "pandas" in str(type(raw)):
            df = raw
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
                df = df.set_index("timestamp").sort_index()
            df = df[["open", "high", "low", "close", "volume"]]
            return [[int(ts.value // 10**6), *map(float, row)] for ts, row in df.itertuples()]
        raise ValueError(f"Format OHLCV inattendu: {type(raw)}")

    def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", since: Any | None = None, limit: int = 1000):
        methods = self._possible_methods(self.client)
        if not methods:
            raise AttributeError("Aucune méthode OHLCV trouvée sur le client Bitget")

        last_err: Exception | None = None
        for mname in methods:
            fn = getattr(self.client, mname)
            for sym in self._sym_variants(symbol):
                for par in self._param_variants(timeframe, self.market_hint):
                    kwargs = dict(par)
                    kwargs.setdefault("symbol", sym)
                    kwargs.setdefault("limit", limit)
                    if since is not None:
                        kwargs.setdefault("since", since)
                    try:
                        _log(f"→ Essai {mname}(kwargs={kwargs})")
                        res = _await_if_needed(fn(**kwargs))
                        rows = self._normalize_rows(res)
                        if rows:
                            unit = "ms" if rows and rows[0][0] > 10_000_000_000 else "s"
                            first = rows[0][0]; last = rows[-1][0]
                            _log(f"✓ OK via {mname} {sym} {par} | n={len(rows)} | "
                                 f"t0={first} {unit}, t1={last} {unit}")
                            return rows
                    except TypeError as e:
                        _log(f"TypeError {mname} {sym} {par}: {e}")
                        last_err = e
                    except Exception as e:
                        _log(f"Erreur {mname} {sym} {par}: {e}")
                        last_err = e
        raise last_err or RuntimeError("Impossible d'obtenir l'OHLCV via le client Bitget")

def ensure_bitget_fetch(exchange: Any, *, market_hint: str | None = None) -> Any:
    """Renvoie l'exchange si fetch_ohlcv existe, sinon un wrapper qui l’implémente. Log debug si BT_DEBUG=1."""
    if hasattr(exchange, "fetch_ohlcv") and callable(getattr(exchange, "fetch_ohlcv")):
        _log("exchange.fetch_ohlcv() déjà présent.")
        return exchange
    _log("exchange.fetch_ohlcv() absent → usage BitgetFetchAdapter.")
    return BitgetFetchAdapter(exchange, market_hint=market_hint)