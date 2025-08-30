from __future__ import annotations
import time, logging
from typing import List, Dict, Any, Optional

from engine.signals.strategy_bridge import evaluate_for
from engine.strategies.runner import load_strategies
from engine.utils.signal_sink import append_signal

LOG = logging.getLogger(__name__)

class PipelineScheduler:
    def __init__(self, symbols: List[str], tfs: List[str], interval: float = 5.0, logger=None):
        self.symbols = symbols
        self.tfs = tfs
        self.interval = interval
        self.log = logger or LOG

        cfg: Dict[str, Any] = load_strategies()      # ← renvoie un seul dict
        self._CFG = cfg
        self._STRATS = cfg.get("strategies", [])

    def _eval_once(self, symbol: str, tf: str, ohlcv: Optional[List[List[float]]] = None) -> Dict[str, Any]:
        res = evaluate_for(symbol=symbol, tf=tf, strategies=self._STRATS, config=self._CFG,
                           ohlcv=ohlcv, logger=self.log)
        sig = res.get("combined", "HOLD")

        # alimente le CSV pour le dashboard (best-effort)
        try:
            items = res.get("items", [])
            details = ";".join(f"{i.get('name')}={i.get('signal')}" for i in items)[:512]
            append_signal({"symbol": symbol, "tf": tf, "signal": sig, "details": details})
        except Exception:
            pass

        self.log.info("pipe-%s-%s | %s close=%s sig=%s", symbol, tf, symbol, res.get("close"), sig)
        return res

    def run(self) -> None:
        self.log.info("Bot démarré avec %s / %s", self.symbols, self.tfs)
        while True:
            t0 = time.time()
            for s in self.symbols:
                for tf in self.tfs:
                    try:
                        self._eval_once(s, tf)
                    except Exception as e:
                        self.log.error("pipeline task error: %s", e, exc_info=True)
            time.sleep(max(0.0, self.interval - (time.time() - t0)))
