# scalp/backtest/engine.py
from __future__ import annotations
import csv, os
from typing import Dict, Any, List
from .metrics import Trade, summarize
from ..risk.manager import compute_size

class BacktestEngine:
    def __init__(self, loader, strategy_fn, cfg: Dict[str, Any], out_dir: str, cash: float, risk_pct: float=0.5):
        self.loader = loader              # sync: fetch_ohlcv(symbol, tf, start, end) -> List[[ts,o,h,l,c,v]]
        self.strategy_fn = strategy_fn
        self.cfg = dict(cfg)
        self.out_dir = out_dir
        self.cash0 = float(cash)
        self.risk_pct = float(risk_pct)
        self.caps_by_symbol = self.cfg.get("caps", {})            # mêmes clés que live
        self.fees_bps = float(self.cfg.get("fees_bps", 0.0))      # optionnel
        self.slippage_bps = float(self.cfg.get("slippage_bps", 0.0))

    def run_pair(self, symbol: str, timeframe: str, start: int, end: int, lookback: int=200) -> Dict[str, Any]:
        ohlcv = self.loader(symbol, timeframe, start, end)
        if len(ohlcv) <= lookback + 1:
            return {"symbol": symbol, "timeframe": timeframe, "error": "not_enough_data"}

        equity = [self.cash0]
        bar_returns = []
        trades: List[Trade] = []
        pos_side = "flat"; pos_qty = 0.0; pos_entry = 0.0
        last_open_ts = None

        os.makedirs(self.out_dir, exist_ok=True)
        eq_path = os.path.join(self.out_dir, f"equity_curve_{symbol}_{timeframe}.csv")
        tr_path = os.path.join(self.out_dir, f"trades_{symbol}_{timeframe}.csv")
        with open(eq_path, "w", newline="") as eqf, open(tr_path, "w", newline="") as trf:
            eqw = csv.writer(eqf); trw = csv.writer(trf)
            eqw.writerow(["ts","equity"])
            trw.writerow(["ts","side","entry","exit","pnl_abs","pnl_pct","dur_min"])

            for i in range(lookback, len(ohlcv)-1):
                window = ohlcv[i-lookback:i+1]
                ts, o, h, l, c, v = window[-1]
                sig = self.strategy_fn(window, self.cfg) or {}
                side = sig.get("side","flat")

                # sortie
                if pos_side != "flat" and (side == "flat" or (side != pos_side and side in ("long","short"))):
                    # slippage + fees simples
                    exit_price = float(c)
                    exit_price *= (1 + (self.slippage_bps/10000.0)) if pos_side=="short" else (1 - (self.slippage_bps/10000.0))
                    pnl_abs = (exit_price - pos_entry) * pos_qty if pos_side=="long" else (pos_entry - exit_price) * pos_qty
                    # frais sur round-trip approx (2 legs)
                    fees = (abs(pos_entry) + abs(exit_price)) * pos_qty * (self.fees_bps/10000.0)
                    pnl_abs -= fees
                    pnl_pct = pnl_abs / max(equity[-1],1e-9)
                    equity.append(equity[-1] + pnl_abs)
                    bar_returns.append(pnl_abs / max(equity[-2],1e-9))
                    dur_min = ((ts - last_open_ts)/60000) if last_open_ts else 0.0
                    trw.writerow([ts, pos_side, pos_entry, exit_price, pnl_abs, pnl_pct, dur_min])
                    trades.append(Trade(ts, pos_side, pos_entry, exit_price, pnl_abs, pnl_pct, dur_min))
                    pos_side, pos_qty, pos_entry, last_open_ts = "flat", 0.0, 0.0, None

                # entrée
                if pos_side == "flat" and side in ("long","short"):
                    price = float(sig.get("entry", c) or c)
                    qty = compute_size(
                        symbol=symbol, price=price, balance_cash=equity[-1],
                        risk_pct=self.risk_pct, caps_by_symbol=self.caps_by_symbol
                    )
                    if qty > 0:
                        pos_side, pos_qty, pos_entry = side, qty, price
                        last_open_ts = ts

                eqw.writerow([ts, equity[-1]])

        start_ts = ohlcv[lookback][0]; end_ts = ohlcv[-1][0]
        m = summarize(trades, equity, bar_returns, start_ts, end_ts)
        m.update({"symbol": symbol, "timeframe": timeframe})
        return m