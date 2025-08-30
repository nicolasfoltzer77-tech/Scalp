# engine/pipelines.py
from __future__ import annotations
import os, time, json, random, threading
from pathlib import Path
from typing import Dict, Any
from engine.utils.logger import get_logger

class Pipeline:
    """
    Boucle simple par (symbol, timeframe):
    - fetch_data: simule un point OHLCV
    - analyze: prend une décision "BUY/SELL/HOLD"
    - execute: écrit une pseudo-ordre si exec_enabled
    - track/record: met à jour un status et un fichier JSON de rapport
    """
    def __init__(self, symbol: str, tf: str, data_dir: str, reports_dir: str, exec_enabled: bool):
        self.symbol, self.tf = symbol, tf
        self.data_dir = Path(data_dir); self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = Path(reports_dir); self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.exec_enabled = exec_enabled
        self.log = get_logger(f"pipe-{symbol}-{tf}")
        self._stop = threading.Event()
        self.state: Dict[str, Any] = {"position": None, "pnl": 0.0}

    def stop(self): self._stop.set()

    # ---- étapes "métier" triviales (à remplacer par ta vraie logique) ----
    def fetch_data(self) -> Dict[str, Any]:
        price = round(20000 + random.random()*50000, 2)
        candle = {"ts": int(time.time()), "symbol": self.symbol, "tf": self.tf, "close": price}
        f = self.data_dir / f"{self.symbol}_{self.tf}.jsonl"
        f.write_text((f.read_text() if f.exists() else "") + json.dumps(candle) + "\n", encoding="utf-8")
        return candle

    def analyze(self, candle: Dict[str, Any]) -> str:
        # signal ultra-simple
        r = random.random()
        if r < 0.33: return "BUY"
        if r < 0.66: return "SELL"
        return "HOLD"

    def execute(self, signal: str, price: float) -> Dict[str, Any] | None:
        if not self.exec_enabled or signal == "HOLD": return None
        order = {"ts": int(time.time()), "symbol": self.symbol, "tf": self.tf, "side": signal, "price": price, "qty": 1}
        # position unique pour la démo
        if signal == "BUY": self.state["position"] = {"side":"LONG","entry":price}
        if signal == "SELL": self.state["position"] = {"side":"SHORT","entry":price}
        return order

    def track_and_record(self, candle: Dict[str, Any], order: Dict[str, Any] | None):
        # met à jour PnL fictif
        if self.state["position"]:
            side = self.state["position"]["side"]; entry = self.state["position"]["entry"]
            pnl = (candle["close"]-entry) if side=="LONG" else (entry-candle["close"])
            self.state["pnl"] = pnl
        # enregistre un mini-rapport pour le dashboard
        rpt = {
            "symbol": self.symbol, "tf": self.tf, "last_close": candle["close"],
            "position": self.state["position"], "pnl": round(self.state["pnl"],2),
            "order": order, "updated_at": candle["ts"]
        }
        (self.reports_dir / f"{self.symbol}_{self.tf}.json").write_text(json.dumps(rpt, indent=2), encoding="utf-8")

    # ---- boucle principale ----
    def run(self, interval_sec: int = 10):
        self.log.info(f"START pipeline {self.symbol} {self.tf} (exec_enabled={self.exec_enabled})")
        while not self._stop.is_set():
            try:
                c = self.fetch_data()
                sig = self.analyze(c)
                ord_ = self.execute(sig, c["close"])
                self.track_and_record(c, ord_)
                self.log.info(f"{self.symbol}-{self.tf} close={c['close']} sig={sig} pnl={self.state['pnl']}")
            except Exception as e:
                self.log.exception(f"error: {e}")
            self._stop.wait(interval_sec)
        self.log.info(f"STOP pipeline {self.symbol} {self.tf}")
