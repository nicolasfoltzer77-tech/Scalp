# scalper/live/watchlist.py
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from scalper.config import load_settings


class WatchlistMode(str, enum.Enum):
    STATIC = "static"         # pairs provided by config
    TOPN   = "topn"           # take top-N by volume/spread (adapter/selection)
    MIXED  = "mixed"          # static + topn


@dataclass
class WatchlistConfig:
    mode: WatchlistMode = WatchlistMode.STATIC
    timeframe: str = "5m"
    refresh_s: int = 300
    topn: int = 10
    static: Sequence[str] = tuple()


class WatchlistManager:
    """
    Small, explicit manager that the orchestrator can use.

    - boot()   -> compute initial pairs
    - pairs    -> current list
    - refresh()-> recompute if mode != STATIC
    """

    def __init__(self, cfg: Optional[WatchlistConfig] = None):
        if cfg is None:
            settings, _secrets = load_settings()
            wl = (settings or {}).get("watchlist", {})  # dict or empty
            mode = str(wl.get("mode", "static")).lower()
            self.cfg = WatchlistConfig(
                mode=WatchlistMode(mode if mode in {"static", "topn", "mixed"} else "static"),
                timeframe=wl.get("timeframe", "5m"),
                refresh_s=int(wl.get("refresh", 300)),
                topn=int(wl.get("topn", 10)),
                static=tuple(wl.get("static", [])),
            )
        else:
            self.cfg = cfg
        self._pairs: List[str] = []

    # ---- public API ---------------------------------------------------------

    def boot(self, exchange=None) -> List[str]:
        """Compute first list of pairs (no network hard‑dependency)."""
        if self.cfg.mode == WatchlistMode.STATIC:
            self._pairs = list(dict.fromkeys([p.strip().upper() for p in self.cfg.static if p]))
            return self._pairs

        # For TOPN/MIXED we try to pull from adapters/selection if available.
        topn_list: List[str] = []
        try:  # lazy import to keep module light
            from scalper.selection.scanner import scan_pairs
            from scalper.selection.momentum import select_active_pairs
            scanned = scan_pairs(exchange=exchange)  # could use public REST
            topn_list = select_active_pairs(scanned, top_n=self.cfg.topn)
        except Exception:
            topn_list = []

        static_list = [p.strip().upper() for p in self.cfg.static or []]
        if self.cfg.mode == WatchlistMode.TOPN:
            base = topn_list
        elif self.cfg.mode == WatchlistMode.MIXED:
            base = list(static_list) + list(topn_list)
        else:  # fallback
            base = static_list

        # Deduplicate while keeping order
        self._pairs = list(dict.fromkeys([p for p in base if p]))
        return self._pairs

    def refresh(self, exchange=None) -> List[str]:
        """Recompute pairs if the mode is dynamic."""
        if self.cfg.mode == WatchlistMode.STATIC:
            return self._pairs
        return self.boot(exchange=exchange)

    # properties --------------------------------------------------------------
    @property
    def pairs(self) -> List[str]:
        return list(self._pairs)

    def __len__(self) -> int:
        return len(self._pairs)

    def __iter__(self) -> Iterable[str]:
        return iter(self._pairs)


def make_watchlist_manager() -> WatchlistManager:
    """Factory kept for older code paths."""
    return WatchlistManager()