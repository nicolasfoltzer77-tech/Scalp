# /opt/scalp/engine/pipeline/runner.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, Optional

from engine.data.loader import load_latest_ohlcv
from engine.signals.strategy_bridge import compute as strat_compute
from engine.exchange.executor import TradeExecutor
from engine.risk.limits import choose_action_from_signal, allowed_size_usdt, should_open

LOG = logging.getLogger("pipeline")

class PipelineScheduler:
    def __init__(self, max_concurrency: int = 8):
        self.max_concurrency = max(1, int(os.environ.get("MAX_CONCURRENCY", max_concurrency)))
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrency, thread_name_prefix="pipe")
        self.trade = TradeExecutor()
        self.last_bar: Dict[Tuple[str,str], int] = {}

    def _eval_once(self, symbol: str, tf: str) -> None:
        ohlcv = load_latest_ohlcv(symbol, tf)  # optionnel
        last_close = None
        last_ts = None
        try:
            if ohlcv:
                last_close = float(ohlcv[-1][4])
                last_ts = int(ohlcv[-1][0])
        except Exception:
            pass

        key = (symbol, tf)
        if last_ts is not None and self.last_bar.get(key) == last_ts:
            # déjà évalué ce bar
            return
        if last_ts is not None:
            self.last_bar[key] = last_ts

        sig, _ = strat_compute(symbol, tf, ohlcv=ohlcv, logger=LOG)
        LOG.info(f"pipe-{symbol}-{tf} | {symbol} {tf} close={last_close} sig={sig} pnl=0.0")

        act = choose_action_from_signal(sig)
        if act != "HOLD" and should_open(symbol, act, last_close):
            if act == "OPEN_LONG":  self.trade.open_long(symbol, tf, last_close)
            elif act == "OPEN_SHORT": self.trade.open_short(symbol, tf, last_close)

    def run_cycle(self, symbols: list[str], tfs: list[str]) -> None:
        tasks = []
        for sy in symbols:
            for tf in tfs:
                tasks.append(self.executor.submit(self._eval_once, sy, tf))
        for f in as_completed(tasks):
            try: f.result()
            except Exception as e:
                LOG.exception(f"pipeline task error: {e}")

    def shutdown(self):
        self.executor.shutdown(wait=False)
