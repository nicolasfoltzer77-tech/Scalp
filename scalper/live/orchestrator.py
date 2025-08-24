# scalper/live/orchestrator.py
from __future__ import annotations
import time
from typing import List, Tuple, Dict, Any
from scalper.live.fetcher import DataFetcher
from scalper.live.runner import JobRunner

class Orchestrator:
    """
    Orchestrateur léger :
      - boucle périodique
      - fetch OHLCV via DataFetcher
      - exécute la stratégie via JobRunner
      - affiche le signal (à brancher plus tard vers RiskManager/OrderService)
    """
    def __init__(
        self,
        *,
        exchange_client: Any,
        strategies_cfg: Dict[str, Any],
        jobs: List[Tuple[str, str]],         # [(symbol, timeframe)]
        interval_sec: int = 60,
        equity: float = 1000.0,
        risk_pct: float = 0.01,
    ) -> None:
        self.fetcher = DataFetcher(exchange_client)
        self.runner = JobRunner(strategies_cfg, equity, risk_pct)
        self.jobs = [(s.upper(), tf) for (s, tf) in jobs]
        self.interval = max(5, int(interval_sec))

    def _tick(self) -> None:
        for symbol, tf in self.jobs:
            try:
                data = self.fetcher.fetch(symbol, tf)
                data_1h = self.fetcher.try_fetch_1h(symbol)
                sig = self.runner.run_once(symbol=symbol, timeframe=tf, ohlcv=data, ohlcv_1h=data_1h)
                if sig is None:
                    print(f"[{symbol}/{tf}] Aucun signal.")
                else:
                    d = sig.as_dict()
                    print(f"[{symbol}/{tf}] side={d['side']} entry={d['entry']:.6f} "
                          f"sl={d['sl']:.6f} tp1={d['tp1']:.6f} tp2={d['tp2']:.6f} "
                          f"score={d['score']} q={d['quality']:.2f} :: {d.get('reasons','')}")
            except Exception as e:
                print(f"[{symbol}/{tf}] ERREUR: {e}")

    def loop(self) -> None:
        print(f"[Orchestrator] jobs={self.jobs} interval={self.interval}s")
        while True:
            t0 = time.time()
            self._tick()
            dt = time.time() - t0
            wait = max(0.0, self.interval - dt)
            time.sleep(wait)