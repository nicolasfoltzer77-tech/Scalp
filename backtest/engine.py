from __future__ import annotations
import csv, os, math
from typing import Dict, Any, List, Tuple
from .metrics import Trade, summarize

class BacktestEngine:
    def __init__(self, loader, strategy_fn, cfg: Dict[str, Any], out_dir: str, cash: float, risk_pct: float=0.5):
        self.loader = loader              # async/sync fetch_ohlcv(symbol, tf, start, end) -> List[[ts, o,h,l,c,v]]
        self.strategy_fn = strategy_fn    # generate_signal(window, cfg) -> dict
        self.cfg = cfg
        self.out_dir = out_dir
        self.cash0 = cash
        self.risk_pct = risk_pct

    def _position_size(self, price: float, balance: float) -> float:
        # taille simple: risque_pct du solde en notionnel; à adapter (min qty exchange, etc.)
        notionnel = balance * self.risk_pct
        return max(0.0, notionnel / max(price, 1e-9))

    def run_pair(self, symbol: str, timeframe: str, start: int, end: int, lookback: int=200) -> Dict[str, Any]:
        ohlcv = self.loader(symbol, timeframe, start, end)  # suppose sync pour simplicité; wrap async si besoin
        if len(ohlcv) <= lookback + 1:
            return {"symbol": symbol, "timeframe": timeframe, "error": "not_enough_data"}

        equity = [self.cash0]
        bar_returns = []
        trades: List[Trade] = []
        pos_side = "flat"; pos_qty = 0.0; pos_entry = 0.0

        # fichiers
        os.makedirs(self.out_dir, exist_ok=True)
        eq_path = os.path.join(self.out_dir, f"equity_curve_{symbol}_{timeframe}.csv")
        tr_path = os.path.join(self.out_dir, f"trades_{symbol}_{timeframe}.csv")
        with open(eq_path, "w", newline="") as eqf, open(tr_path, "w", newline="") as trf:
            eqw = csv.writer(eqf); trw = csv.writer(trf)
            eqw.writerow(["ts","equity"])
            trw.writerow(["ts","side","entry","exit","pnl_abs","pnl_pct","dur_min"])

            for i in range(lookback, len(ohlcv)-1):
                window = ohlcv[i-lookback:i+1]  # inclusif i
                ts, o, h, l, c, v = window[-1]
                sig = self.strategy_fn(window, self.cfg) or {}
                side = sig.get("side","flat")

                # close position if opposite signal or flat
                if pos_side != "flat" and (side == "flat" or (side != pos_side and side in ("long","short"))):
                    exit_price = c
                    pnl_abs = (exit_price - pos_entry) * pos_qty if pos_side=="long" else (pos_entry - exit_price) * pos_qty
                    pnl_pct = pnl_abs / max(equity[-1],1e-9)
                    equity.append(equity[-1] + pnl_abs)
                    bar_returns.append(pnl_abs / max(equity[-2],1e-9))
                    dur_min = (ts - trades[-1].ts)/60000 if trades else 0.0
                    trw.writerow([ts, pos_side, pos_entry, exit_price, pnl_abs, pnl_pct, dur_min])
                    trades.append(Trade(ts, pos_side, pos_entry, exit_price, pnl_abs, pnl_pct, dur_min))
                    pos_side, pos_qty, pos_entry = "flat", 0.0, 0.0
                # open position if flat -> signal long/short
                if pos_side == "flat" and side in ("long","short"):
                    price = c
                    qty = self._position_size(price, equity[-1])
                    if qty > 0:
                        pos_side, pos_qty, pos_entry = side, qty, price
                        # pas d'écriture ici; on log à la sortie

                eqw.writerow([ts, equity[-1]])

        start_ts = ohlcv[lookback][0]; end_ts = ohlcv[-1][0]
        m = summarize(trades, equity, bar_returns, start_ts, end_ts)
        m.update({"symbol": symbol, "timeframe": timeframe})
        return m