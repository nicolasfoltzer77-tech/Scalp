# scalp/live/watchlist.py
from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, Awaitable, List, Optional, Sequence, Tuple

DBG = os.getenv("WATCHLIST_DEBUG", "0") == "1"
def _dprint(msg: str):
    if DBG:
        print(f"[watchlist:debug] {msg}")


class WatchlistManager:
    """
    Génération de watchlist TOP N :
      - mode='local'  : calcule TOPN via OHLCV (volume quote ~ 24h)
      - mode='api'    : utilise un endpoint bulk (si disponible)
      - mode='static' : valeurs fixes (TOP_SYMBOLS ou défaut)
    """

    def __init__(
        self,
        exchange,
        *,
        only_suffix: str = "USDT",
        top_n: int = 10,
        period_s: float = 120.0,
        on_update: Optional[Callable[[Sequence[str]], None]] = None,
        safe_call: Optional[Callable[[Callable[[], Any], str], Any]] = None,
        ohlcv_fetch: Optional[Callable[[str, str, int], Awaitable[List[Any]]]] = None,
    ) -> None:
        self.exchange = exchange
        self.only_suffix = only_suffix.upper() if only_suffix else ""
        self.top_n = top_n
        self.period_s = period_s
        self.on_update = on_update
        self._safe = safe_call or (lambda f, _label: f())
        self._running = False
        self._ohlcv_fetch = ohlcv_fetch
        self.mode = (os.getenv("WATCHLIST_MODE") or "static").lower()  # static | api | local

    # ---------- extraction API générique ----------
    @staticmethod
    def _extract_items(payload: Any) -> List[Any]:
        if payload is None:
            return []
        if isinstance(payload, dict):
            for k in ("data", "result", "tickers", "items", "list", "tickerList", "records"):
                v = payload.get(k)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    # un niveau de plus
                    for kk in ("data", "result", "tickers", "items", "list", "tickerList", "records"):
                        vv = v.get(kk)
                        if isinstance(vv, list):
                            return vv
            return []
        if isinstance(payload, (list, tuple)):
            return list(payload)
        return []

    @staticmethod
    def _norm_symbol_and_volume(item: Any) -> Tuple[str, float]:
        if isinstance(item, dict):
            s = (item.get("symbol") or item.get("instId") or "").replace("_", "").upper()
            vol = item.get("volume", item.get("usdtVolume", item.get("quoteVolume", 0.0)))
            try:
                v = float(vol or 0.0)
            except Exception:
                v = 0.0
            return s, v
        try:
            seq = list(item)
            s = str(seq[0]).replace("_", "").upper() if seq else ""
            v = float(seq[1]) if len(seq) > 1 else 0.0
            return s, v
        except Exception:
            return "", 0.0

    def _pick_top(self, payload: Any) -> List[str]:
        items = self._extract_items(payload)
        pairs: List[Tuple[str, float]] = []
        for it in items:
            s, v = self._norm_symbol_and_volume(it)
            if not s:
                continue
            if self.only_suffix and not s.endswith(self.only_suffix):
                continue
            pairs.append((s, v))
        pairs.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in pairs[: self.top_n]]

    # ---------- TOPN local via OHLCV ----------
    async def _build_top_local(self) -> List[str]:
        if not self._ohlcv_fetch:
            return []
        # candidates : env ou liste par défaut (~40 liquides)
        raw = (os.getenv("TOP_CANDIDATES") or "")
        if raw:
            candidates = [s.strip().upper().replace("_", "") for s in raw.split(",") if s.strip()]
        else:
            candidates = [
                "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","TRXUSDT","TONUSDT","LTCUSDT",
                "LINKUSDT","ARBUSDT","OPUSDT","APTUSDT","SUIUSDT","PEPEUSDT","AVAXUSDT","DOTUSDT","MATICUSDT","ATOMUSDT",
                "NEARUSDT","SEIUSDT","RUNEUSDT","TIAUSDT","WIFUSDT","JUPUSDT","ICPUSDT","FILUSDT","ETCUSDT","BCHUSDT",
                "XLMUSDT","HBARUSDT","EOSUSDT","TRBUSDT","AAVEUSDT","UNIUSDT","FLOWUSDT","RNDRUSDT","ORDIUSDT","SEIUSDT",
            ]
        sem = asyncio.Semaphore(int(os.getenv("WATCHLIST_LOCAL_CONC", "5")))

        async def score(sym: str) -> Tuple[str, float]:
            async with sem:
                try:
                    rows = await self._ohlcv_fetch(sym, "1m", 1440)
                    tot = 0.0
                    for r in rows or []:
                        if isinstance(r, dict):
                            tot += float(r.get("close", 0.0)) * float(r.get("volume", 0.0))
                        else:
                            tot += float(r[4]) * float(r[5])  # [.., close, volume]
                    return sym, tot
                except Exception:
                    return sym, 0.0

        scores = await asyncio.gather(*(score(s) for s in candidates))
        scores.sort(key=lambda x: x[1], reverse=True)
        top = [s for s, v in scores if s.endswith(self.only_suffix)][: self.top_n]
        if DBG:
            _dprint(f"local scores top={top[:5]}")
        return top

    # ---------- public ----------
    async def boot_topN(self) -> List[str]:
        # 1) local (réel) si demandé
        if self.mode == "local":
            try:
                top = await self._build_top_local()
                if top:
                    if self.on_update: self.on_update(top)
                    return top
            except Exception as e:
                _dprint(f"local mode error: {e!r}")

        # 2) api (si un bulk existe un jour)
        if self.mode in ("api", "local"):
            try:
                payload = await self._safe(lambda: self.exchange.get_ticker(None), "get_ticker(None)")
                _dprint(f"payload via get_ticker(None): type={type(payload).__name__}")
                top = self._pick_top(payload)
                if top:
                    if self.on_update: self.on_update(top)
                    return top
            except Exception as e:
                _dprint(f"api mode error: {e!r}")

        # 3) fallback statique
        env_syms = (os.getenv("TOP_SYMBOLS") or "").replace(" ", "")
        top = [s for s in env_syms.split(",") if s] if env_syms else \
              ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","TRXUSDT","TONUSDT","LTCUSDT"]
        top = [s.replace("_", "").upper() for s in top][: self.top_n]
        if DBG:
            _dprint(f"using static TOP{len(top)} = {top}")
        if self.on_update: self.on_update(top)
        return top

    async def task_auto_refresh(self):
        self._running = True
        while self._running:
            try:
                top = await self.boot_topN()
                _dprint(f"refresh -> {top}")
            except Exception as e:
                print(f"[watchlist] refresh error: {e!r}")
            await asyncio.sleep(self.period_s)

    def stop(self):
        self._running = False