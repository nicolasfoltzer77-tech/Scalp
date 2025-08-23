# scalp/backtest/runner.py
from __future__ import annotations
import json, os, asyncio
from typing import List, Dict, Callable
from .engine import BacktestEngine
from ..signals.factory import load_signal

def default_loader(fetch_sync: Callable) -> Callable:
    return fetch_sync

class BacktestRunner:
    def __init__(self, loader, out_dir: str, strategy: str, cfg: Dict,
                 cash: float, risk_pct: float, max_conc: int=4):
        self.loader = loader
        self.out_dir = out_dir
        self.strategy_fn = load_signal(strategy)
        self.cfg = dict(cfg)
        self.cash = cash
        self.risk_pct = risk_pct
        self.sem = asyncio.Semaphore(max_conc)

    async def _run_one(self, symbol: str, timeframe: str, start: int, end: int) -> Dict:
        async with self.sem:
            engine = BacktestEngine(self.loader, self.strategy_fn, self.cfg,
                                    os.path.join(self.out_dir, f"{symbol}_{timeframe}"),
                                    self.cash, self.risk_pct)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, engine.run_pair, symbol, timeframe, start, end)

    async def run_all(self, symbols: List[str], timeframes: List[str], start: int, end: int) -> Dict:
        os.makedirs(self.out_dir, exist_ok=True)
        tasks = [self._run_one(sym, tf, start, end) for sym in symbols for tf in timeframes]
        results = await asyncio.gather(*tasks)

        per_symbol_best = {}
        for r in results:
            if "error" in r: continue
            sym = r["symbol"]
            if sym not in per_symbol_best or r["score"] > per_symbol_best[sym]["score"]:
                per_symbol_best[sym] = r

        top_overall = sorted([r for r in results if "error" not in r], key=lambda x: x["score"], reverse=True)[:10]
        proposal = {
            "per_symbol_best": {k: {"timeframe": v["timeframe"], "score": v["score"], "pf": v["pf"],
                                    "winrate": v["winrate"], "maxdd": v["maxdd"]}
                                for k,v in per_symbol_best.items()},
            "top_overall": top_overall,
            "suggested_timeframes": {k: v["timeframe"] for k,v in per_symbol_best.items()},
            "note": "Suggestion basée sur score composite (WR, PF, MaxDD, Sharpe)."
        }
        with open(os.path.join(self.out_dir, "metrics.json"), "w") as f:
            json.dump({"results": results, "proposal": proposal}, f, indent=2)
        return {"results": results, "proposal": proposal}