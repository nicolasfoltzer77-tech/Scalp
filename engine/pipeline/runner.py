from __future__ import annotations
import time, logging
from typing import List, Dict, Any, Optional

from engine.strategies.runner import load_strategies
from engine.signals.strategy_bridge import evaluate_for

from engine.utils.signal_sink import append_signal                    # legacy -> signals.csv
from engine.utils.signal_sink_factored import append_signal_factored  # nouveau -> signals_f.csv
from tools.load_pairs import load_pairs

LOG = logging.getLogger("pipeline")

class PipelineScheduler:
    """
    Boucle principale : évalue (symbol × tf), écrit les signaux (legacy + factorisé),
    et recharge la watchlist depuis pairs.txt régulièrement.
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

        cfg: Dict[str, Any] = load_strategies()
        self._CFG: Dict[str, Any] = cfg
        self._STRATS: List[Dict[str, Any]] = cfg.get("strategies", [])

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
        if new_pairs and new_pairs != self.symbols:
            self.log.info("Watchlist mise à jour (%d → %d paires)", len(self.symbols), len(new_pairs))
            self.symbols = new_pairs

    def _eval_once(self, symbol: str, tf: str, ohlcv: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        res = evaluate_for(symbol=symbol, tf=tf,
                           strategies=self._STRATS, config=self._CFG,
                           ohlcv=ohlcv, logger=self.log)

        # --- Signal combiné (legacy) ---
        sig = res.get("combined", "HOLD")
        items = res.get("items", [])
        details = ";".join(f"{i.get('name')}={i.get('signal')}" for i in items)[:512]
        try:
            append_signal({"symbol": symbol, "tf": tf, "signal": sig, "details": details})
        except Exception as e:
            self.log.error("append_signal legacy failed: %s", e)

        # --- Version factorisée ---
        ts = int(res.get("ts") or time.time())
        # On récupère des valeurs numériques si dispo (sinon None)
        metrics = res.get("metrics", {})  # idéalement fourni par evaluate_for
        rsi_val = metrics.get("rsi")
        ema_val = metrics.get("ema")
        sma_val = metrics.get("sma")

        # Calcul d'un score factorisé simple si pas fourni par evaluate_for
        factor = res.get("factor")
        if factor is None:
            # transforme les sous-signaux en -1/0/+1
            def to_factor(v: str) -> int:
                v = (v or "").upper()
                if v in ("BUY","LONG","BULL"):  return 1
                if v in ("SELL","SHORT","BEAR"): return -1
                return 0
            f_parts = [to_factor(i.get("signal")) for i in items]
            factor = sum(f_parts) if f_parts else 0

        why = ",".join(f"{i.get('name')}:{i.get('signal')}" for i in items)[:180]

        try:
            append_signal_factored({
                "ts": ts, "symbol": symbol, "tf": tf, "signal": sig,
                "rsi": rsi_val, "ema": ema_val, "sma": sma_val,
                "factor": factor, "why": why
            })
        except Exception as e:
            self.log.error("append_signal_factored failed: %s", e)

        self.log.info("pipe-%s-%s sig=%s factor=%s", symbol, tf, sig, factor)
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
