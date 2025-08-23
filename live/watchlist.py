# scalp/live/watchlist.py
from __future__ import annotations
import os
import asyncio
from typing import Any, Callable, List, Optional, Sequence, Tuple

DBG = os.getenv("WATCHLIST_DEBUG", "0") == "1"

def _dprint(msg: str):
    if DBG:
        print(f"[watchlist:debug] {msg}")

class WatchlistManager:
    """
    TOP N par volume (suffixe USDT par défaut).
    - boot_topN(): construit la liste au démarrage (avec fallbacks agressifs)
    - task_auto_refresh(): rafraîchit périodiquement
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
    ) -> None:
        self.exchange = exchange
        self.only_suffix = only_suffix.upper() if only_suffix else ""
        self.top_n = top_n
        self.period_s = period_s
        self.on_update = on_update
        self._running = False
        # safe_call doit être une coroutine fournie par l'orchestrateur (self._safe)
        # qui gère sync/async + retries.
        self._safe = safe_call or (lambda f, _label: f())

    # -------- helpers parsing --------
    @staticmethod
    def _extract_items(payload: Any) -> List[Any]:
        if payload is None:
            return []
        if isinstance(payload, dict):
            for k in (
                "data", "result", "tickers", "items", "list",
                "tickerList", "records"
            ):
                v = payload.get(k)
                if v:
                    return v if isinstance(v, list) else []
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

    # -------- boot / refresh --------
    async def boot_topN(self) -> List[str]:
        """
        Essaie plusieurs endpoints pour récupérer les tickers.
        Si rien ne sort, fallback -> ['BTCUSDT', 'ETHUSDT'].
        """
        payload = None
        top: List[str] = []

        # 1) Méthodes "all tickers" si présentes (sync ou async)
        for name in ("get_tickers", "list_tickers", "all_tickers"):
            fn = getattr(self.exchange, name, None)
            if callable(fn):
                try:
                    payload = await self._safe(fn, f"{name}")  # ← AWAIT obligatoire
                    _dprint(f"payload via {name}: type={type(payload).__name__}")
                    top = self._pick_top(payload)
                    if top:
                        break
                except Exception as e:
                    _dprint(f"{name} error: {e!r}")
                    payload = None

        # 2) Variantes de get_ticker(arg) (renvoie souvent une coroutine)
        if not top:
            get_ticker = getattr(self.exchange, "get_ticker", None)
            if callable(get_ticker):
                for arg in (None, "ALL", "", "*"):
                    try:
                        payload = await self._safe(lambda a=arg: get_ticker(a), f"get_ticker({arg})")  # ← AWAIT
                        _dprint(f"payload via get_ticker({arg}): type={type(payload).__name__}")
                        top = self._pick_top(payload)
                        if top:
                            break
                    except Exception as e:
                        _dprint(f"get_ticker({arg}) error: {e!r}")
                        payload = None

        # 3) Décision finale
        if not top:
            top = ["BTCUSDT", "ETHUSDT"]
            _dprint("fallback to ['BTCUSDT','ETHUSDT']")

        if self.on_update:
            self.on_update(top)
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