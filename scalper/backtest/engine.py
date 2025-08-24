# scalper/backtest/engine.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import csv
import os
from dataclasses import dataclass, asdict
from scalper.strategy.factory import resolve_signal_fn
from scalper.core.signal import Signal
from scalper.backtest.position_sizing import position_size_from_signal, fees_cost

@dataclass
class Trade:
    symbol: str
    timeframe: str
    side: str
    entry_ts: int
    exit_ts: int
    entry: float
    exit: float
    qty: float
    pnl: float
    pnl_after_fees: float
    reasons: str

def _read_csv(path: str) -> Dict[str, List[float]]:
    cols = ("timestamp","open","high","low","close","volume")
    out = {k: [] for k in cols}
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            for k in cols:
                out[k].append(float(row[k]))
    return out

def _slice(d: Dict[str, List[float]], end_idx: int) -> Dict[str, List[float]]:
    return {k: v[: end_idx + 1] for k, v in d.items()}

class BacktestEngine:
    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str,
        data: Dict[str, List[float]],           # OHLCV complet
        equity_start: float = 1_000.0,
        risk_pct: float = 0.01,
        fees_bps: float = 6.0,                   # 6 bps round-trip par défaut
        warmup: int = 230,                       # pour EMA200/MACD
        strategies_cfg: Dict[str, Any],
        data_1h: Optional[Dict[str, List[float]]] = None,
    ):
        self.symbol = symbol.upper()
        self.tf = timeframe
        self.data = data
        self.data_1h = data_1h
        self.equity = float(equity_start)
        self.start_equity = float(equity_start)
        self.risk_pct = float(risk_pct)
        self.fees_bps = float(fees_bps)
        self.warmup = int(warmup)
        self.cfg = strategies_cfg
        self.trades: List[Trade] = []
        self.signals_rows: List[Dict[str, Any]] = []

        self.signal_fn = resolve_signal_fn(self.symbol, self.tf, self.cfg)

    def run(self) -> Tuple[float, List[Trade]]:
        n = len(self.data["close"])
        pos_open: Optional[Signal] = None
        pos_qty: float = 0.0
        entry_idx: int = -1

        for i in range(self.warmup, n):
            window = _slice(self.data, i)
            window_1h = _slice(self.data_1h, self._map_1h_index(i)) if self.data_1h else None

            sig = self.signal_fn(
                symbol=self.symbol,
                timeframe=self.tf,
                ohlcv=window,
                equity=self.equity,
                risk_pct=self.risk_pct,
                ohlcv_1h=window_1h,
            )

            if sig:
                self.signals_rows.append(sig.as_dict())

            # Si aucune position, tenter l'entrée
            if pos_open is None and sig is not None:
                qty = position_size_from_signal(self.equity, sig, self.risk_pct * max(0.25, sig.quality))
                if qty <= 0:
                    continue
                pos_open = sig
                pos_qty = qty
                entry_idx = i
                continue

            # Gestion position ouverte
            if pos_open is not None:
                # Check TP/SL sur la bougie suivante (pas de futur)
                hi = self.data["high"][i]
                lo = self.data["low"][i]
                exit_price: Optional[float] = None
                tp1 = pos_open.tp1 or pos_open.entry
                tp2 = pos_open.tp2 or pos_open.entry

                # logique: TP1 -> moitié + BE; TP2 -> full
                half_closed = False
                be = pos_open.entry

                if pos_open.side == "long":
                    # Stop
                    if lo <= pos_open.sl:
                        exit_price = pos_open.sl
                    # TP1
                    elif hi >= tp1:
                        pnl_half = (tp1 - pos_open.entry) * (pos_qty * 0.5)
                        fees = fees_cost(tp1 * (pos_qty * 0.5), self.fees_bps)
                        self.equity += pnl_half - fees
                        pos_qty *= 0.5
                        half_closed = True
                        pos_open.sl = be  # BE
                    # TP2
                    if hi >= tp2:
                        exit_price = tp2

                else:  # short
                    if hi >= pos_open.sl:
                        exit_price = pos_open.sl
                    elif lo <= tp1:
                        pnl_half = (pos_open.entry - tp1) * (pos_qty * 0.5)
                        fees = fees_cost(tp1 * (pos_qty * 0.5), self.fees_bps)
                        self.equity += pnl_half - fees
                        pos_qty *= 0.5
                        half_closed = True
                        pos_open.sl = be
                    if lo <= tp2:
                        exit_price = tp2

                # sortie partielle non suivie de TP2/SL : on continue
                if exit_price is None and half_closed:
                    continue

                # fermeture
                if exit_price is not None:
                    pnl = (exit_price - pos_open.entry) * pos_qty if pos_open.side == "long" else (pos_open.entry - exit_price) * pos_qty
                    fees = fees_cost(exit_price * pos_qty, self.fees_bps)
                    pnl_after = pnl - fees
                    self.equity += pnl_after

                    tr = Trade(
                        symbol=self.symbol, timeframe=self.tf, side=pos_open.side,
                        entry_ts=int(self.data["timestamp"][entry_idx]), exit_ts=int(self.data["timestamp"][i]),
                        entry=pos_open.entry, exit=exit_price, qty=pos_qty,
                        pnl=pnl, pnl_after_fees=pnl_after,
                        reasons="|".join(pos_open.reasons),
                    )
                    self.trades.append(tr)
                    pos_open = None
                    pos_qty = 0.0
                    entry_idx = -1

        return self.equity, self.trades

    def _map_1h_index(self, i_main: int) -> int:
        """Mapping naïf: suppose que self.data_1h est alignée en temps croissant.
        Ici, on prend l'index 1h correspondant au timestamp le plus proche inférieur ou égal."""
        if not self.data_1h:
            return 0
        ts = self.data["timestamp"][i_main]
        arr = self.data_1h["timestamp"]
        # recherche linéaire (suffisant pour test; remplaçable par bisect)
        j = 0
        while j + 1 < len(arr) and arr[j + 1] <= ts:
            j += 1
        return j

    # --- Helpers d'E/S ---
    @staticmethod
    def load_csv(path: str) -> Dict[str, List[float]]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"CSV OHLCV introuvable: {path}")
        return _read_csv(path)

    def save_results(self, out_dir: str = "backtest_out") -> None:
        os.makedirs(out_dir, exist_ok=True)
        # signals.csv
        if self.signals_rows:
            sig_path = os.path.join(out_dir, f"signals_{self.symbol}_{self.tf}.csv")
            keys = sorted(self.signals_rows[0].keys())
            with open(sig_path, "w", newline="", encoding="utf-8") as f:
                import csv
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                for row in self.signals_rows:
                    w.writerow(row)
        # trades.csv
        if self.trades:
            tr_path = os.path.join(out_dir, f"trades_{self.symbol}_{self.tf}.csv")
            with open(tr_path, "w", newline="", encoding="utf-8") as f:
                import csv
                w = csv.writer(f)
                w.writerow(["symbol","timeframe","side","entry_ts","exit_ts","entry","exit","qty","pnl","pnl_after_fees","reasons"])
                for t in self.trades:
                    w.writerow([t.symbol,t.timeframe,t.side,t.entry_ts,t.exit_ts,t.entry,t.exit,t.qty,t.pnl,t.pnl_after_fees,t.reasons])

    def summary(self) -> Dict[str, float]:
        eq = self.equity
        ret = (eq / self.start_equity - 1.0) * 100.0
        n = len(self.trades)
        wins = sum(1 for t in self.trades if t.pnl_after_fees > 0)
        winrate = (wins / n * 100.0) if n else 0.0
        return {"equity_end": eq, "return_pct": ret, "trades": float(n), "winrate_pct": winrate}