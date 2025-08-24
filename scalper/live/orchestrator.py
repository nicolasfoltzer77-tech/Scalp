import time
from scalper.live.fetcher import DataFetcher
from scalper.live.runner import JobRunner

class Orchestrator:
    def __init__(self, exchange_client, strategies_cfg, jobs, interval_sec=60,
                 equity=1000.0, risk_pct=0.01):
        self.fetcher = DataFetcher(exchange_client)
        self.runner = JobRunner(strategies_cfg, equity, risk_pct)
        self.jobs = jobs
        self.interval = max(5, int(interval_sec))

    def loop(self):
        print(f"[Orchestrator] jobs={self.jobs} interval={self.interval}s")
        while True:
            t0 = time.time()
            for symbol, tf in self.jobs:
                try:
                    data = self.fetcher.fetch(symbol, tf)
                    data_1h = self.fetcher.fetch(symbol, "1h")
                    sig = self.runner.run_once(symbol, tf, data, data_1h)
                    if sig:
                        print(f"[{symbol}/{tf}] signal={sig.side} entry={sig.entry} "
                              f"sl={sig.sl} tp1={sig.tp1} score={sig.score}")
                    else:
                        print(f"[{symbol}/{tf}] Aucun signal.")
                except Exception as e:
                    print(f"[{symbol}/{tf}] ERREUR: {e}")
            dt = time.time() - t0
            time.sleep(max(0.0, self.interval - dt))