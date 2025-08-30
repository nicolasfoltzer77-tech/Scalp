#!/usr/bin/env python3
import time
import logging

from engine.pipeline.runner import PipelineScheduler
from engine.strategies.runner import load_strategies
from engine.signals.strategy_bridge import evaluate_for

# Logger global
LOG = logging.getLogger("bot")

# Charger stratégies (une ou deux valeurs selon la version)
_LOADED = load_strategies()
if isinstance(_LOADED, tuple) and len(_LOADED) == 2:
    _STRATS, _CFG = _LOADED
else:
    _STRATS, _CFG = _LOADED, {}

class Bot:
    def __init__(self, symbols, tfs, interval=10):
        self.symbols = symbols
        self.tfs = tfs
        self.interval = interval
        self.log = LOG

    def _eval_once(self, symbol, tf, ohlcv=None):
        try:
            res = evaluate_for(
                symbol=symbol,
                tf=tf,
                strategies=_STRATS,
                config=_CFG,
                ohlcv=ohlcv,
                logger=self.log
            )
            if isinstance(res, str):
                sig, details = res, {}
            else:
                sig = res.get("combined") or res.get("signal") or "HOLD"
                details = res

            close = None
            if isinstance(details, dict):
                close = details.get("close")
                if close is None:
                    o = details.get("ohlcv")
                    if isinstance(o, list) and o and isinstance(o[-1], (list, tuple)):
                        close = o[-1][-1]

            self.log.info("pipe-%s-%s | %s-%s close=%s sig=%s",
                          symbol, tf, symbol, tf, close, sig)

            return {"symbol": symbol, "tf": tf, "sig": sig, "details": details}

        except Exception as e:
            self.log.error("pipeline task error: %s", e, exc_info=True)
            return {"symbol": symbol, "tf": tf, "sig": "ERR", "details": {}}

    def run(self):
        self.log.info("Bot démarré avec %s / %s", self.symbols, self.tfs)
        while True:
            for s in self.symbols:
                for tf in self.tfs:
                    self._eval_once(s, tf)
            time.sleep(self.interval)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    import sys
    symbols = ["BTCUSDT", "ETHUSDT"] if len(sys.argv) < 2 else sys.argv[1:]
    tfs = ["1m", "5m", "15m"]
    Bot(symbols, tfs, interval=10).run()
