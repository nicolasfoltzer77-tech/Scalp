from __future__ import annotations

import time
import logging
from typing import List, Dict, Any, Optional

from engine.signals.strategy_bridge import evaluate_for
from engine.strategies.runner import load_strategies

# charge toutes les stratégies
_STRATS, _CFG = load_strategies()

LOG = logging.getLogger("runner")


class PipelineScheduler:
    def __init__(self, symbols: List[str], tfs: List[str], interval: int = 30, logger=None):
        self.symbols = symbols
        self.tfs = tfs
        self.interval = interval
        self.log = logger or LOG

    def _eval_once(self, symbol: str, tf: str, ohlcv: Optional[List[List[float]]] = None):
        try:
            res = evaluate_for(
                symbol=symbol,
                tf=tf,
                strategies=_STRATS,
                config=_CFG,
                ohlcv=ohlcv,
                logger=self.log,
            )
            sig = res.get("combined")
            return {"symbol": symbol, "tf": tf, "sig": sig, "details": res}
        except Exception as e:
            self.log.error("pipeline task error: %s", e, exc_info=True)
            return {"symbol": symbol, "tf": tf, "sig": "ERR", "details": {}}

    def run_forever(self):
        while True:
            cycle = []
            for sym in self.symbols:
                for tf in self.tfs:
                    r = self._eval_once(sym, tf)
                    cycle.append(r)
            self.log.info("cycle done: %s", cycle)
            time.sleep(self.interval)
