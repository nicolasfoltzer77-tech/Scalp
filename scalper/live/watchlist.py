# scalper/live/watchlist.py
from __future__ import annotations

import asyncio
import os
import statistics
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, List, Optional, Sequence

# Types
OHLCVFetcher = Callable[[str, str], Awaitable[Sequence[Sequence[float]]]]
# attendu: fetch(symbol, timeframe="5m", limit=?), renvoie [[ts,o,h,l,c,v], ...]

QUIET = int(os.getenv("QUIET", "0") or "0")

DEFAULT_SHORTLIST = [
    # shortlist liquides futures USDT (à ajuster)
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT",
    "ADAUSDT", "LTCUSDT", "AVAXUSDT", "LINKUSDT", "TRXUSDT", "UNIUSDT",
    "SHIBUSDT", "OPUSDT", "APTUSDT", "ETCUSDT", "NEARUSDT", "FILUSDT",
    "SUIUSDT", "TONUSDT",
]

def _parse_csv_env(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name, "")
    if not raw:
        return list(default)
    return [s.strip().upper() for s in raw.split(",") if s.strip()]

def _log(msg: str) -> None:
    if not QUIET:
        print(f"[watchlist] {msg}", flush=True)

@dataclass
class WatchlistManager:
    # Public API compatible avec orchestrator
    mode: str
    top_candidates: List[str]
    local_conc: int
    ohlcv_fetch: OHLCVFetcher
    timeframe: str = "5m"
    refresh_sec: int = int(os.getenv("WATCHLIST_REFRESH_SEC", "300") or "300")
    topn: int = int(os.getenv("TOPN", "10") or "10")

    # NOTE: le constructeur accepte **watchlist_mode** pour compatibilité
    def __init__(
        self,
        *,
        watchlist_mode: str = "static",
        top_candidates: str | Iterable[str] | None = None,
        local_conc: int = int(os.getenv("WATCHLIST_LOCAL_CONC", "5") or "5"),
        ohlcv_fetch: OHLCVFetcher | None = None,
        timeframe: str = os.getenv("WATCHLIST_TIMEFRAME", "5m"),
        refresh_sec: int = int(os.getenv("WATCHLIST_REFRESH_SEC", "300") or "300"),
        topn: int = int(os.getenv("TOPN", "10") or "10"),
    ):
        self.mode = (watchlist_mode or "static").lower()
        if isinstance(top_candidates, str):
            self.top_candidates = _parse_csv_env("", []) if top_candidates == "" else (
                [s.strip().upper() for s in top_candidates.split(",") if s.strip()]
            )
        elif top_candidates is None:
            self.top_candidates = _parse_csv_env("TOP_CANDIDATES", DEFAULT_SHORTLIST)
        else:
            self.top_candidates = [s.strip().upper() for s in top_candidates]

        self.local_conc = int(local_conc)
        self.ohlcv_fetch = ohlcv_fetch or (lambda sym, timeframe="5m", limit=150: asyncio.sleep(0.0))  # type: ignore
        self.timeframe = timeframe
        self.refresh_sec = int(refresh_sec)
        self.topn = int(topn)

        if self.mode not in ("static", "local", "api"):
            _log(f"mode inconnu '{self.mode}', fallback -> static")
            self.mode = "static"

        _log(f"init: mode={self.mode} topn={self.topn} timeframe={self.timeframe} refresh={self.refresh_sec}s")

    # ----------------------------- PUBLIC ---------------------------------

    async def boot_topN(self) -> List[str]:
        """Calcul initial de la watchlist TOPN."""
        if self.mode == "static":
            syms = self._static_symbols()
            _log(f"boot got (static): {syms[:self.topn]}")
            return syms[:self.topn]
        elif self.mode == "local":
            syms = await self._local_topN()
            _log(f"boot got (local): {syms}")
            return syms
        else:
            # placeholder API -> pour l’instant même comportement que static
            syms = self._static_symbols()
            _log(f"boot got (api placeholder->static): {syms[:self.topn]}")
            return syms[:self.topn]

    async def task_auto_refresh(self):
        """
        Async generator: recalcule périodiquement la watchlist et la renvoie.
        Usage:
            async for top in watchlist.task_auto_refresh():
                ...
        """
        while True:
            try:
                if self.mode == "local":
                    syms = await self._local_topN()
                elif self.mode == "static":
                    syms = self._static_symbols()[:self.topn]
                else:
                    syms = self._static_symbols()[:self.topn]  # placeholder
                yield syms
            except Exception as e:
                _log(f"refresh error: {e}")
            await asyncio.sleep(max(15, self.refresh_sec))

    # ----------------------------- MODES ----------------------------------

    def _static_symbols(self) -> List[str]:
        # priorise TOP_SYMBOLS si défini, sinon shortlist/candidats
        top_symbols_env = _parse_csv_env("TOP_SYMBOLS", [])
        if top_symbols_env:
            return top_symbols_env
        return list(self.top_candidates or DEFAULT_SHORTLIST)

    async def _local_topN(self) -> List[str]:
        """
        Classement local via 'somme(close*volume)' sur ~24h pour la shortlist.
        """
        shortlist = self._static_symbols()
        if not shortlist:
            shortlist = list(DEFAULT_SHORTLIST)

        async def score_symbol(sym: str) -> tuple[str, float]:
            try:
                # on récupère ~24h pour 5m -> ~288 bougies (on prend 300 pour marge)
                raw = await self.ohlcv_fetch(sym, self.timeframe, limit=300)  # type: ignore[arg-type]
                total = 0.0
                for r in raw or []:
                    # r: [ts, o, h, l, c, v]
                    c = float(r[4]); v = float(r[5])
                    total += c * v
                return sym, total
            except Exception:
                return sym, 0.0

        # Concurrence limitée
        sem = asyncio.Semaphore(max(1, self.local_conc))
        results: list[tuple[str, float]] = []

        async def worker(s: str):
            async with sem:
                results.append(await score_symbol(s))

        await asyncio.gather(*(worker(s) for s in shortlist))
        results.sort(key=lambda kv: kv[1], reverse=True)
        top = [s for s, _ in results[: self.topn]]
        return top