# -*- coding: utf-8 -*-
"""
Adaptateur Bitget unifié pour Scalp:
- supporte mix (UMCBL/UMCBL perps) et spot
- gère les 2 routes de chandelles: /candles (récent) et /history-candles (historique)
- normalise la réponse (liste brute ou enveloppe {"data": [...]})
- fournit DataFrame prêt à l’emploi pour le moteur
"""
from __future__ import annotations
import time
from typing import List, Sequence, Optional, Dict, Any

import requests
import pandas as pd


BASE = "https://api.bitget.com"

# timeframe -> secondes
TF_SEC = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900,
    "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400,
}

class BitgetError(RuntimeError):
    pass


class BitgetClient:
    """
    market:
      - "umcbl" (perp USDT-M futures)
      - "spbl"  (spot)
    """
    def __init__(self, market: str = "umcbl", timeout: int = 15):
        self.market = market.lower()
        if self.market not in ("umcbl", "spbl"):
            raise ValueError("market doit être 'umcbl' (futures) ou 'spbl' (spot)")
        self.timeout = timeout

    # ---------- helpers

    def _pair(self, symbol: str) -> str:
        """Formate le symbole selon le type de marché."""
        s = symbol.upper().replace("-", "").replace("/", "")
        if self.market == "umcbl":
            # Futures USDT perp = BTCUSDT_UMCBL
            if not s.endswith("_UMCBL"):
                s = f"{s}_UMCBL"
        else:
            # Spot = BTCUSDT_SPBL
            if not s.endswith("_SPBL"):
                s = f"{s}_SPBL"
        return s

    def _ok(self, resp: requests.Response) -> List[List[str]]:
        """Normalise la réponse en liste de lignes OHLCV."""
        if resp.status_code != 200:
            raise BitgetError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            js = resp.json()
        except Exception as e:
            raise BitgetError(f"Invalid JSON: {e}")

        # Les API Bitget renvoient parfois directement une liste,
        # parfois un dict {"code": "...", "data": [...]}
        if isinstance(js, list):
            return js
        if isinstance(js, dict):
            data = js.get("data")
            if isinstance(data, list):
                return data
            # cas erreur enveloppé
            code = str(js.get("code"))
            if code not in ("00000", "0", "200"):
                raise BitgetError(f"Bitget error {code}: {js}")
            return data or []
        # autre format = pas normal
        raise BitgetError(f"Réponse inattendue: {type(js).__name__}")

    # ---------- routes

    def _route_candles(self) -> str:
        """Route « récente » selon le marché."""
        if self.market == "umcbl":
            return "/api/mix/v1/market/candles"
        return "/api/spot/v1/market/candles"

    def _route_history(self) -> str:
        """Route « historique » selon le marché."""
        if self.market == "umcbl":
            return "/api/mix/v1/market/history-candles"
        return "/api/spot/v1/market/history-candles"

    # ---------- fetch OHLCV (liste de lignes brutes)

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
    ) -> List[Sequence[str]]:
        """
        Retourne une liste de lignes [ts, open, high, low, close, vol, quote_vol?]
        (les APIs Bitget renvoient parfois 6 colonnes; on comble quote_volume à '0' si absent)
        """
        if timeframe not in TF_SEC:
            raise ValueError(f"timeframe non supporté: {timeframe}")
        if limit <= 0:
            return []

        pair = self._pair(symbol)
        gran = TF_SEC[timeframe]
        step_ms = gran * 1000

        out: List[Sequence[str]] = []

        # 1) on tente la route "candles" (récent)
        url_recent = BASE + self._route_candles()
        params_recent = {"symbol": pair, "granularity": gran, "limit": min(limit, 1000)}
        r = requests.get(url_recent, params=params_recent, timeout=self.timeout)
        try:
            recent = self._ok(r)
        except BitgetError:
            recent = []

        if recent:
            out.extend(recent[::-1])  # API renvoie généralement du plus récent au plus ancien

        # 2) s'il manque du passé, on complète avec "history-candles" (fenêtrage par temps)
        need = max(0, limit - len(out))
        if need > 0:
            url_hist = BASE + self._route_history()
            end = int(time.time() * 1000)
            while need > 0:
                start = end - step_ms * min(need, 1000)
                params = {
                    "symbol": pair,
                    "granularity": gran,
                    "startTime": start,
                    "endTime": end,
                }
                hresp = requests.get(url_hist, params=params, timeout=self.timeout)
                chunk = self._ok(hresp)
                if not chunk:
                    break
                out.extend(chunk[::-1])
                end = int(chunk[0][0]) - step_ms
                need = max(0, limit - len(out))
                if len(chunk) < 2:
                    break
                time.sleep(0.08)

        # tronque et normalise 7 colonnes
        out = out[:limit]
        norm: List[List[str]] = []
        for row in out:
            # certaines routes n’ont que 6 champs
            if len(row) == 6:
                ts, o, h, l, c, v = row
                norm.append([ts, o, h, l, c, v, "0"])
            else:
                # garde tel quel (7 colonnes)
                norm.append(list(row[:7]))
        return norm

    # ---------- DataFrame « prêt moteur »

    def fetch_ohlcv_df(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 500,
    ) -> pd.DataFrame:
        rows = self.fetch_ohlcv(symbol, timeframe, limit)
        df = pd.DataFrame(rows, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "quote_volume"
        ])
        # conversions
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        for col in ("open", "high", "low", "close", "volume", "quote_volume"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df.sort_values("timestamp").reset_index(drop=True)
