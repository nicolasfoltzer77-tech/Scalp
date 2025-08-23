# scalper/exchange/bitget_ccxt.py
from __future__ import annotations

import asyncio
import csv
import os
import time
from typing import Any, List, Optional

# CCXT async
try:
    import ccxt.async_support as ccxt
except Exception as e:  # noqa: BLE001
    raise RuntimeError("CCXT n'est pas installé. Fais `pip install ccxt`.") from e


def _now_ms() -> int:
    return int(time.time() * 1000)


class BitgetExchange:
    """
    Échange Bitget via CCXT (async) avec cache CSV local.
    - Orienté SPOT pour simplifier (BTCUSDT, ETHUSDT, ...).
    - fetch_ohlcv(symbol, timeframe, limit) -> list[list] façon CCXT:
        [[ts, open, high, low, close, volume], ...]
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        password: Optional[str] = None,  # Bitget a souvent "password" (API passphrase)
        data_dir: str = "/notebooks/data",
        use_cache: bool = True,
        min_fresh_seconds: int = 0,  # fraicheur minimale requise (0 = on accepte tout)
        spot: bool = True,           # True = SPOT (recommandé ici)
    ) -> None:
        self.data_dir = data_dir
        self.use_cache = use_cache
        self.min_fresh = int(min_fresh_seconds)
        self.spot = spot

        os.makedirs(self.data_dir, exist_ok=True)

        # Instance CCXT (async)
        self.ex = ccxt.bitget({
            "apiKey": api_key or "",
            "secret": secret or "",
            "password": password or "",
            "enableRateLimit": True,
            # CCXT timeframe natif (pas besoin de rajouter des headers…)
        })

        # Pré‑charge les marchés SPOT pour résoudre correctement symboles
        self._markets_task: Optional[asyncio.Task[Any]] = None

    async def _ensure_markets(self) -> None:
        if self._markets_task is None:
            self._markets_task = asyncio.create_task(self.ex.load_markets())
        await self._markets_task

    # ---------- CSV cache ----------
    def _csv_path(self, symbol: str, timeframe: str) -> str:
        safe = symbol.replace("/", "").replace(":", "")
        return os.path.join(self.data_dir, f"{safe}-{timeframe}.csv")

    def _read_cache(self, path: str) -> List[List[float]]:
        if not os.path.exists(path):
            return []
        rows: List[List[float]] = []
        try:
            with open(path, "r", newline="") as f:
                rd = csv.reader(f)
                for r in rd:
                    if not r:
                        continue
                    # ts, o, h, l, c, v
                    try:
                        rows.append([
                            int(r[0]),
                            float(r[1]),
                            float(r[2]),
                            float(r[3]),
                            float(r[4]),
                            float(r[5]),
                        ])
                    except Exception:
                        # on ignore les lignes corrompues
                        continue
        except Exception:
            return []
        return rows

    def _write_cache(self, path: str, data: List[List[float]]) -> None:
        # On ré‑écrit intégralement (simple et sûr)
        tmp = path + ".tmp"
        with open(tmp, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerows(data)
        os.replace(tmp, path)

    # ---------- API publique pour orchestrateur ----------
    async def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int, since: Optional[int] = None
    ) -> List[List[float]]:
        """
        Conformité orchestrateur : signature (symbol, timeframe, limit).
        Retour CCXT OHLCV. Utilise cache si dispo/assez frais, sinon CCXT.
        """
        await self._ensure_markets()

        # Bitget (spot) symbol format CCXT: "BTC/USDT"
        ccxt_symbol = symbol.replace("USDT", "/USDT")
        cache_path = self._csv_path(symbol, timeframe)

        # 1) Cache
        if self.use_cache:
            cached = self._read_cache(cache_path)
            if cached:
                # fraicheur = diff entre maintenant et ts dernière bougie
                last_ts = int(cached[-1][0])
                if self.min_fresh == 0 or (_now_ms() - last_ts) <= self.min_fresh * 1000:
                    # suffisant => on retourne la fin
                    if len(cached) >= limit:
                        return cached[-limit:]
                    # pas assez, on essaiera de compléter via CCXT plus bas
                # sinon: on tentera de rafraîchir plus loin

        # 2) Remote via CCXT
        # CCXT fetch_ohlcv: since=None, limit=…  (since en ms)
        # On demande 'limit' bougies; si cache partiel, on pourra fusionner ensuite.
        params: dict[str, Any] = {}
        if self.spot is True:
            params["type"] = "spot"  # ccxt bitget accepte 'type' pour certain endpoints

        try:
            ohlcv = await self.ex.fetch_ohlcv(ccxt_symbol, timeframe, since=since, limit=limit, params=params)
        except Exception as e:  # noqa: BLE001
            # En cas d’échec remote: si on a du cache, on le renvoie quand même
            cached = self._read_cache(cache_path) if self.use_cache else []
            if cached:
                return cached[-limit:]
            raise RuntimeError(f"Bitget CCXT fetch_ohlcv failed for {symbol} {timeframe}: {e}") from e

        # 3) Merge simple cache + remote et ré‑écrit (sans doublons sur ts)
        if self.use_cache:
            base = self._read_cache(cache_path)
            merged = _merge_ohlcv(base, ohlcv)
            self._write_cache(cache_path, merged)
            # retourne la fin
            return merged[-limit:]

        return ohlcv[-limit:]

    async def close(self) -> None:
        try:
            await self.ex.close()
        except Exception:
            pass


def _merge_ohlcv(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """
    Fusionne deux listes OHLCV par timestamp, en écrasant a par b sur collision.
    """
    if not a:
        return list(b)
    if not b:
        return list(a)

    # index rapide par ts
    by_ts: dict[int, List[float]] = {int(row[0]): row for row in a}
    for row in b:
        by_ts[int(row[0])] = row
    return [by_ts[k] for k in sorted(by_ts)]