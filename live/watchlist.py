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
        # Doit être une coroutine fournie par l’orchestrateur (self._safe)
        self._safe = safe_call or (lambda f, _label: f())

    # ---------- recherche récursive de la 1ère liste ----------
    def _find_first_list(self, obj: Any, depth: int = 0, path: str = "$") -> List[Any]:
        """
        Explore récursivement (profondeur <=3) pour trouver une liste exploitable.
        On privilégie les clés usuelles: data, result, tickers, items, list, tickerList, records.
        """
        if obj is None or depth > 3:
            return []

        # cas direct: déjà une liste
        if isinstance(obj, (list, tuple)):
            _dprint(f"found list at path {path} (len={len(obj)})")
            return list(obj)

        if isinstance(obj, dict):
            # 1) clés prioritaires
            preferred = ["data", "result", "tickers", "items", "list", "tickerList", "records"]
            for k in preferred:
                if k in obj:
                    v = obj.get(k)
                    if isinstance(v, (list, tuple)):
                        _dprint(f"found list at path {path}.{k} (len={len(v)})")
                        return list(v)
                    if isinstance(v, dict):
                        res = self._find_first_list(v, depth + 1, f"{path}.{k}")
                        if res:
                            return res
            # 2) sinon on parcourt toutes les valeurs
            for k, v in obj.items():
                if isinstance(v, (list, tuple)):
                    _dprint(f"found list at path {path}.{k} (len={len(v)})")
                    return list(v)
                if isinstance(v, dict):
                    res = self._find_first_list(v, depth + 1, f"{path}.{k}")
                    if res:
                        return res
        return []

    # ---------- normalisation d’un item ticker ----------
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
        items = self._find_first_list(payload, 0, "$")
        if DBG and isinstance(payload, dict):
            _dprint(f"top picking from dict keys={list(payload.keys())[:8]}")
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

    # ---------- boot / refresh ----------
        async def boot_topN(self) -> List[str]:
        """
        Fallback robuste : si l'API ne renvoie rien d'exploitable,
        on lit TOP_SYMBOLS depuis l'env, sinon un TOP10 par défaut.
        """
        # 1) Essai API (garde si fonctionnel chez toi un jour)
        try:
            payload = await self._safe(lambda: self.exchange.get_ticker(None), "get_ticker(None)")
            top = self._pick_top(payload)
            if top:
                if self.on_update: self.on_update(top)
                return top
        except Exception:
            pass

        # 2) Env override
        env_syms = (os.getenv("TOP_SYMBOLS") or "").replace(" ", "")
        if env_syms:
            top = [s for s in env_syms.split(",") if s]
            top = [s.replace("_","").upper() for s in top][: self.top_n]
        else:
            # 3) TOP10 par défaut (futures USDT liquides)
            top = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
                   "DOGEUSDT","ADAUSDT","TRXUSDT","TONUSDT","LTCUSDT"][: self.top_n]

        # log debug
        if os.getenv("WATCHLIST_DEBUG","0") == "1":
            print(f"[watchlist:debug] using static TOP{len(top)} = {top}")

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