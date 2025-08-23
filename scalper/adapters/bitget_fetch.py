# scalper/adapters/bitget_fetch.py
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Iterable, Optional


# -------- utils temps --------

_TF_TO_SECS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400,
}
_TF_TO_MIX = {  # granularity pour mix
    "1m": "1min", "3m": "3min", "5m": "5min", "15m": "15min",
    "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day",
}
_TF_TO_SPOT = {  # period pour spot
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


# -------- adaptateur --------

class BitgetFetchAdapter:
    """
    Ajoute une méthode CCXT-like `fetch_ohlcv(symbol, timeframe='5m', since=None, limit=1000)`
    au-dessus d'un client Bitget existant (sync ou async).

    Essaie automatiquement plusieurs méthodes/paramètres courants :
    - fetch_ohlcv (déjà présent) -> direct
    - get_candlesticks / candlesticks / candles / klines
    - mix_get_candles (futures UM) / spot_get_candles
    Paramètres possibles : timeframe | granularity | period | interval | k | type ; limit ; since.
    Essaie aussi des variantes de symbole : <SYM>, <SYM>_UMCBL, <SYM>_SPBL (si besoin).
    Retour : [[ts, o, h, l, c, v], ...]
    """

    def __init__(self, client: Any, *, market_hint: str | None = None):
        self.client = client
        self.market_hint = (market_hint or "").lower() or None

        # si le client a déjà fetch_ohlcv → on l'utilise tel quel
        if hasattr(client, "fetch_ohlcv") and callable(getattr(client, "fetch_ohlcv")):
            self.fetch_ohlcv = getattr(client, "fetch_ohlcv")  # type: ignore[attr-defined]

    # --- helpers nom méthode/params ---------------------------------------

    @staticmethod
    def _possible_methods(client: Any) -> list[str]:
        names = dir(client)
        candidates = [
            "get_candlesticks", "candlesticks", "get_candles", "candles",
            "klines", "get_klines", "kline",
            "mix_get_candles", "mix_candles",
            "spot_get_candles", "spot_candles",
            "market_candles", "public_candles",
        ]
        return [n for n in candidates if n in names and callable(getattr(client, n))]

    @staticmethod
    def _sym_variants(sym: str) -> list[str]:
        s = sym.upper()
        out = [s]
        if not s.endswith("_UMCBL"):
            out.append(f"{s}_UMCBL")
        if not s.endswith("_SPBL"):
            out.append(f"{s}_SPBL")
        return out

    @staticmethod
    def _param_variants(timeframe: str, market_hint: Optional[str]) -> list[dict]:
        secs = _TF_TO_SECS.get(timeframe, 300)
        mix = _TF_TO_MIX.get(timeframe, "5min")
        spot = _TF_TO_SPOT.get(timeframe, "5min")
        # on prépare plusieurs jeux de paramètres possibles
        params = []
        # génériques
        params.append({"timeframe": timeframe})
        params.append({"interval": timeframe})
        params.append({"k": secs})
        # mix/spot
        params.append({"granularity": mix})
        params.append({"period": spot})
        # hints
        if market_hint == "mix":
            params.insert(0, {"granularity": mix})
        if market_hint == "spot":
            params.insert(0, {"period": spot})
        return params

    # --- normalisation du retour ------------------------------------------

    @staticmethod
    def _normalize_rows(raw: Any) -> list[list[float]]:
        if raw is None:
            raise ValueError("OHLCV vide")
        # dict {data:[...]}
        if isinstance(raw, dict) and "data" in raw:
            raw = raw["data"]
        # déjà list of lists
        if isinstance(raw, (list, tuple)) and raw and isinstance(raw[0], (list, tuple)):
            out = []
            for r in raw:
                ts = int(str(r[0]))
                o, h, l, c, v = map(float, (r[1], r[2], r[3], r[4], r[5]))
                out.append([ts, o, h, l, c, v])
            return out
        # pandas.DataFrame
        try:
            import pandas as pd  # local import
            if isinstance(raw, pd.DataFrame):
                df = raw.copy()
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, infer_datetime_format=True)
                    df = df.set_index("timestamp").sort_index()
                df = df[["open", "high", "low", "close", "volume"]]
                return [[int(ts.value // 10**6), *map(float, row)] for ts, row in df.itertuples()]
        except Exception:
            pass
        raise ValueError(f"Format OHLCV inattendu: {type(raw)}")

    # --- API publique ------------------------------------------------------

    def fetch_ohlcv(self, symbol: str, timeframe: str = "5m", since: Any | None = None, limit: int = 1000):
        """
        Essaie en cascade toutes les signatures/méthodes possibles sur le client Bitget,
        jusqu'à obtenir un OHLCV normalisé.
        """
        methods = []
        # si le client a fetch_ohlcv direct et qu'on n'a pas été surchargé (cas rare)
        if hasattr(self.client, "fetch_ohlcv") and type(getattr(self.client, "fetch_ohlcv")).__name__ != "function":
            methods.append("fetch_ohlcv")
        methods += self._possible_methods(self.client)
        if not methods:
            raise AttributeError("Aucune méthode OHLCV trouvée sur le client Bitget")

        # on essaye pour chaque méthode, plusieurs symboles et variantes de paramètres
        last_err: Exception | None = None
        for mname in methods:
            fn = getattr(self.client, mname)
            for sym in self._sym_variants(symbol):
                for par in self._param_variants(timeframe, self.market_hint):
                    # injecte limit et since si la signature les accepte
                    # tentative en kwargs
                    kwargs = dict(par)
                    kwargs.setdefault("symbol", sym)
                    kwargs.setdefault("limit", limit)
                    if since is not None:
                        kwargs.setdefault("since", since)
                    try:
                        res = _await_if_needed(fn(**kwargs))
                        rows = self._normalize_rows(res)
                        if rows:
                            return rows
                    except TypeError:
                        # essaie en positionnel (symbol, param_timeframe?, since?, limit?)
                        try:
                            args = [sym]
                            # param temps : timeframe/granularity/period/k/secs
                            if "timeframe" in par: args.append(par["timeframe"])
                            elif "granularity" in par: args.append(par["granularity"])
                            elif "period" in par: args.append(par["period"])
                            elif "k" in par: args.append(par["k"])
                            # since/limit
                            if "since" in fn.__code__.co_varnames:  # best effort
                                args.append(since)
                                args.append(limit)
                            elif "limit" in fn.__code__.co_varnames:
                                args.append(limit)
                            res = _await_if_needed(fn(*args))
                            rows = self._normalize_rows(res)
                            if rows:
                                return rows
                        except Exception as e2:
                            last_err = e2
                            continue
                    except Exception as e:
                        last_err = e
                        continue
        raise last_err or RuntimeError("Impossible d'obtenir l'OHLCV via le client Bitget")


def ensure_bitget_fetch(exchange: Any, *, market_hint: str | None = None) -> Any:
    """
    Si `exchange` possède déjà `fetch_ohlcv`, on le renvoie tel quel.
    Sinon, on renvoie un wrapper `BitgetFetchAdapter(exchange)`.
    """
    if hasattr(exchange, "fetch_ohlcv") and callable(getattr(exchange, "fetch_ohlcv")):
        return exchange
    return BitgetFetchAdapter(exchange, market_hint=market_hint)