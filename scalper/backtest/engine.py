# scalper/backtest/engine.py
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from scalper.strategy import generate_signal
from scalper.trade_utils import compute_position_size
from scalper.exchange.fees import get_fee

OHLCVLoader = Callable[[str, str, Optional[str], Optional[str]], pd.DataFrame]


@dataclass
class Fill:
    ts: pd.Timestamp
    symbol: str
    side: str       # "long" | "short" | "flat"
    price: float
    qty: float
    fee: float
    reason: str     # "entry"|"tp"|"sl"|"exit"|"reverse"|"final_exit"


@dataclass
class Trade:
    symbol: str
    side: str
    entry_ts: pd.Timestamp
    entry_px: float
    qty: float
    exit_ts: pd.Timestamp
    exit_px: float
    fee_entry: float
    fee_exit: float
    pnl: float
    pnl_pct: float


@dataclass
class EquityPoint:
    ts: pd.Timestamp
    equity: float


def _apply_slippage(price: float, side: str, slippage_bps: float) -> float:
    if slippage_bps <= 0:
        return price
    mult = 1.0 + (slippage_bps / 10_000.0)
    return price * (mult if side in ("buy", "long") else 1.0 / mult)


def _hit_tp_sl(row: pd.Series, side: str, tp: float, sl: float) -> Tuple[bool, str, float]:
    high, low, close = float(row.high), float(row.low), float(row.close)
    if side == "long":
        if low <= sl <= high:
            return True, "sl", sl
        if low <= tp <= high:
            return True, "tp", tp
        return False, "", close
    else:
        if low <= tp <= high:
            return True, "tp", tp
        if low <= sl <= high:
            return True, "sl", sl
        return False, "", close


def run_single(
    *,
    symbol: str,
    timeframe: str,
    loader: OHLCVLoader,
    start: str | None = None,
    end: str | None = None,
    initial_cash: float = 10_000.0,
    risk_pct: float = 0.005,
    slippage_bps: float = 1.5,
    taker: bool = True,
    quiet: bool = True,
) -> Dict[str, object]:
    df = loader(symbol, timeframe, start, end).copy()
    if df.empty:
        raise ValueError(f"Pas de données pour {symbol} {timeframe}")
    df.columns = [c.lower() for c in df.columns]
    for c in ("open", "high", "low", "close", "volume"):
        if c not in df.columns:
            raise ValueError(f"OHLCV invalide: colonne {c} manquante")

    fee_rate = get_fee(symbol, "taker" if taker else "maker")

    equity = float(initial_cash)
    pos_side: str = "flat"
    pos_qty: float = 0.0
    entry_px: float = 0.0
    fee_entry: float = 0.0
    sl: float = math.nan
    tp: float = math.nan

    eq: List[EquityPoint] = []
    fills: List[Fill] = []
    closed: List[Trade] = []

    for ts, row in df.iterrows():
        ts = pd.Timestamp(ts)

        # gérer SL/TP quand en position
        if pos_side in ("long", "short"):
            hit, reason, exec_px = _hit_tp_sl(row, pos_side, tp, sl)
            if hit:
                px = _apply_slippage(exec_px, "sell" if pos_side == "long" else "buy", slippage_bps)
                fee = abs(px * pos_qty) * fee_rate
                pnl = (px - entry_px) * pos_qty if pos_side == "long" else (entry_px - px) * pos_qty
                equity += pnl - fee
                fills.append(Fill(ts, symbol, "flat", px, -pos_qty if pos_side == "long" else pos_qty, fee, reason))
                closed.append(
                    Trade(
                        symbol=symbol, side=pos_side, entry_ts=ts, entry_px=entry_px, qty=pos_qty,
                        exit_ts=ts, exit_px=px, fee_entry=fee_entry, fee_exit=fee,
                        pnl=pnl - fee_entry - fee,
                        pnl_pct=((equity / initial_cash) - 1.0) * 100.0 if initial_cash else 0.0,
                    )
                )
                pos_side, pos_qty, entry_px, sl, tp, fee_entry = "flat", 0.0, 0.0, math.nan, math.nan, 0.0

        # signal de la stratégie live
        sig = generate_signal(
            symbol=symbol,
            ohlcv=df.loc[:ts].tail(300),
            equity=equity,
            risk_pct=risk_pct,
        )
        if sig and getattr(sig, "side", None) and pos_side == "flat":
            side = sig.side  # "long"|"short"
            px = _apply_slippage(float(sig.price), "buy" if side == "long" else "sell", slippage_bps)
            qty = float(getattr(sig, "qty", 0.0)) or compute_position_size(equity, px, risk_pct, symbol=symbol)
            if qty > 0:
                fee = abs(px * qty) * fee_rate
                pos_side, pos_qty, entry_px = side, qty, px
                sl = float(getattr(sig, "sl", px * (0.995 if side == "long" else 1.005)))
                tp = float(getattr(sig, "tp", getattr(sig, "tp1", px * (1.005 if side == "long" else 0.995))))
                fee_entry = fee
                equity -= fee
                fills.append(Fill(ts, symbol, side, px, qty if side == "long" else -qty, fee, "entry"))

        eq.append(EquityPoint(ts, equity))

    # sortie forcée fin de série
    if pos_side in ("long", "short"):
        last_ts = pd.Timestamp(df.index[-1])
        px = _apply_slippage(float(df["close"].iloc[-1]), "sell" if pos_side == "long" else "buy", slippage_bps)
        fee = abs(px * pos_qty) * fee_rate
        pnl = (px - entry_px) * pos_qty if pos_side == "long" else (entry_px - px) * pos_qty
        equity += pnl - fee
        fills.append(Fill(last_ts, symbol, "flat", px, -pos_qty if pos_side == "long" else pos_qty, fee, "final_exit"))
        closed.append(
            Trade(
                symbol=symbol, side=pos_side, entry_ts=last_ts, entry_px=entry_px, qty=pos_qty,
                exit_ts=last_ts, exit_px=px, fee_entry=fee_entry, fee_exit=fee,
                pnl=pnl - fee_entry - fee, pnl_pct=((equity / initial_cash) - 1.0) * 100.0 if initial_cash else 0.0,
            )
        )

    eq_df = pd.DataFrame([asdict(e) for e in eq])
    tr_df = pd.DataFrame([asdict(t) for t in closed])
    fills_df = pd.DataFrame([asdict(f) for f in fills])

    metrics = {
        "symbol": symbol,
        "timeframe": timeframe,
        "initial_cash": initial_cash,
        "final_equity": float(eq_df["equity"].iloc[-1] if not eq_df.empty else initial_cash),
        "return_pct": float(((eq_df["equity"].iloc[-1] / initial_cash) - 1.0) * 100.0 if initial_cash and not eq_df.empty else 0.0),
        "n_trades": int(len(tr_df)),
        "win_rate_pct": float((tr_df["pnl"] > 0).mean() * 100.0) if not tr_df.empty else 0.0,
        "avg_trade_pnl": float(tr_df["pnl"].mean()) if not tr_df.empty else 0.0,
        "max_dd_pct": float(((eq_df["equity"].cummax() - eq_df["equity"]) / eq_df["equity"].cummax()).max() * 100.0) if not eq_df.empty else 0.0,
    }

    return {"equity_curve": eq_df, "trades": tr_df, "fills": fills_df, "metrics": metrics}