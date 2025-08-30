from __future__ import annotations

import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Union

from engine.signals.strategy_bridge import evaluate_for
from engine.strategies.runner import load_strategies

LOG = logging.getLogger("runner")


def _normalize_strats_cfg(
    ret: Union[Tuple, List, Dict[str, Any], None]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Rend robuste le chargement stratégies/config quel que soit
    le format retourné par load_strategies().
    Acceptés :
      - (strategies, config)
      - (strategies, config, *extra)
      - (strategies,)
      - {"strategies": [...], "config": {...}}
    """
    if ret is None:
        return [], {}

    # tuple / list
    if isinstance(ret, (tuple, list)):
        if len(ret) >= 2:
            return ret[0], ret[1]
        if len(ret) == 1:
            return ret[0], {}
        return [], {}

    # dict-like
    if isinstance(ret, dict):
        strats = ret.get("strategies") or ret.get("strats") or []
        cfg = ret.get("config") or {}
        return strats, cfg

    # fallback
    return [], {}


# ----- charge stratégies + config (robuste)
try:
    _STRATS, _CFG = _normalize_strats_cfg(load_strategies())
    LOG.info("strategies loaded: %d | cfg keys: %s",
             len(_STRATS), list(_CFG.keys())[:6])
except Exception as e:
    LOG.exception("failed to load strategies, continue with empty set: %s", e)
    _STRATS, _CFG = [], {}


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
