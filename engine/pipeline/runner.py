from __future__ import annotations
import os, time, logging
from typing import List, Dict, Any, Optional

from engine.signals.strategy_bridge import evaluate_for
from engine.strategies.runner import load_strategies
from engine.utils.signal_sink import append_signal
from tools.load_pairs import load_pairs  # ← pairs.txt

LOG = logging.getLogger("pipeline")

class PipelineScheduler:
    """
    Boucle principale : évalue (symbol × tf), écrit les signaux CSV,
    et recharge la watchlist depuis pairs.txt toutes les N secondes.
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        tfs: Optional[List[str]] = None,
        interval_sec: float = 5.0,
        reload_pairs_sec: float = 60.0,
        logger: Optional[logging.Logger] = None,
    ):
        self.tfs = tfs or ["1m","5m","15m"]
        self.interval = interval_sec
        self.reload_pairs_sec = reload_pairs_sec
        self.log = logger or LOG

        # stratégies/config (un seul dict)
        cfg: Dict[str, Any] = load_strategies()
        self._CFG: Dict[str, Any] = cfg
        self._STRATS: List[Dict[str, Any]] = cfg.get("strategies", [])

        # pairs initiales
        self.symbols: List[str] = symbols or load_pairs()
        self._last_reload = 0.0

        self.log.info("Scheduler prêt | symbols=%s | tfs=%s | interval=%.1fs | reload_pairs=%.0fs",
                      self.symbols, self.tfs, self.interval, self.reload_pairs_sec)

    def _maybe_reload_pairs(self):
        now = time.time()
        if now - self._last_reload < self.reload_pairs_sec:
            return
        self._last_reload = now
        new_pairs = load_pairs()
        if not new_pairs:
            return
        if new_pairs != self.symbols:
            self.log.info("Watchlist mise à jour (%d → %d paires)", len(self.symbols), len(new_pairs))
            self.log.debug("Anciennes: %s", self.symbols)
            self.log.debug("Nouvelles: %s", new_pairs)
            self.symbols = new_pairs

    def _eval_once(self, symbol: str, tf: str, ohlcv: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        res = evaluate_for(symbol=symbol, tf=tf,
                           strategies=self._STRATS, config=self._CFG,
                           ohlcv=ohlcv, logger=self.log)
        sig = res.get("combined", "HOLD")
        # écriture CSV (dashboard)
        try:
            items = res.get("items", [])
            details = ";".join(f"{i.get('name')}={i.get('signal')}" for i in items)[:512]
            append_signal({"symbol": symbol, "tf": tf, "signal": sig, "details": details})
        except Exception:
            pass
        self.log.info("pipe-%s-%s sig=%s", symbol, tf, sig)
        return res

    def run(self) -> None:
        self.log.info("Bot démarré avec %s / %s", self.symbols, self.tfs)
        while True:
            self._maybe_reload_pairs()
            t0 = time.time()
            for s in self.symbols:
                for tf in self.tfs:
                    try:
                        self._eval_once(s, tf)
                    except Exception as e:
                        self.log.error("pipeline task error: %s", e, exc_info=True)
            time.sleep(max(0.0, self.interval - (time.time() - t0)))
