# live/watchlist.py
from __future__ import annotations
import asyncio
from typing import Any, List, Sequence, Tuple, Callable, Optional

class WatchlistManager:
    """
    Service de sélection des meilleures paires.
    - boot_top10(): construit la liste TOP10 immédiatement
    - task_auto_refresh(): tâche périodique pour maintenir la liste
    On fournit des hooks pour propager les changements (on_update).
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
        # safe_call(factory, label) -> Any ; fourni par l’orchestrateur pour gérer retries
        self._safe = safe_call or (lambda f, _label: f())

    # ---------- Normalisation ticker ----------
    @staticmethod
    def _extract_items(payload: Any) -> List[Any]:
        if payload is None:
            return []
        if isinstance(payload, dict):
            for k in ("data", "result", "tickers", "items", "list"):
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
        # tolérance minimale sur formats séquentiels
        try:
            seq = list(item)
            s = str(seq[0]).replace("_", "").upper() if seq else ""
            v = float(seq[1]) if len(seq) > 1 else 0.0
            return s, v
        except Exception:
            return "", 0.0

    # ---------- Boot: top N immédiat ----------
    async def boot_top10(self) -> List[str]:
        payload = await self._safe(lambda: self.exchange.get_ticker(None), "get_tickers_boot")  # type: ignore
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
        top = [s for s, _ in pairs[: self.top_n]]
        if self.on_update:
            self.on_update(top)
        return top

    # ---------- Tâche périodique ----------
    async def task_auto_refresh(self):
        self._running = True
        while self._running:
            try:
                await self.boot_top10()
            except Exception as e:
                print(f"[watchlist] refresh error: {e!r}")
            await asyncio.sleep(self.period_s)

    def stop(self):
        self._running = False