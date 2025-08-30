# /opt/scalp/engine/exchange/executor.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, json, pathlib, logging
from typing import Optional

LOG = logging.getLogger("executor")

class TradeExecutor:
    def __init__(self):
        self.dry_run = os.environ.get("DRY_RUN", "1") == "1"
        self.enable_log = os.environ.get("ENABLE_LOG_TRADES", "1") == "1"
        self.log_path = pathlib.Path("/opt/scalp/logs/trades.log")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, payload: dict):
        if self.enable_log:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _emit(self, action: str, symbol: str, tf: str, price: Optional[float]):
        LOG.info(f"[trade] {symbol}@{tf} → {action} price={price} dry_run={self.dry_run}")
        self._write({"ts": int(time.time()*1000), "symbol": symbol, "tf": tf,
                     "action": action, "price": price, "dry_run": self.dry_run})

    # Map simple — à brancher vers Bitget si DRY_RUN=0
    def open_long(self, symbol: str, tf: str, price: Optional[float]): self._emit("OPEN_LONG",  symbol, tf, price)
    def open_short(self, symbol: str, tf: str, price: Optional[float]): self._emit("OPEN_SHORT", symbol, tf, price)
    def close_all(self, symbol: str, tf: str, price: Optional[float]):  self._emit("CLOSE_ALL",  symbol, tf, price)
