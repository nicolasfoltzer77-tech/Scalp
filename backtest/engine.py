"""Simple backtest engine with dynamic risk and trailing stops.

This module provides two helpers:
- the original :class:`BacktestEngine` for individual trades,
- :func:`backtest_symbol` used by the multi pair backtester.  The latter
  intentionally relies only on the Python standard library so it can run in
  restricted environments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Sequence, Tuple
import math
import random

from scalp.metrics import calc_pnl_pct
from scalp.risk import adjust_risk_pct
from scalp.strategy import generate_signal

__all__ = [
    "dynamic_risk_pct",
    "apply_trailing",
    "BacktestEngine",
    "run_backtest",
    "backtest_symbol",
]


# ---------------------------------------------------------------------------
# Simple trade engine used by existing tests
# ---------------------------------------------------------------------------


def dynamic_risk_pct(risk_pct: float, win_streak: int, loss_streak: int) -> float:
    """Return a risk percentage adjusted by recent performance."""

    return adjust_risk_pct(risk_pct, win_streak, loss_streak)


def apply_trailing(
    side: str,
    high: float,
    low: float,
    exit_price: float,
    trail_pct: float,
) -> float:
    """Apply a trailing stop to an exit price."""

    if trail_pct <= 0:
        return exit_price

    side = side.lower()
    if side == "long":
        trail_stop = high * (1 - trail_pct)
        return trail_stop if exit_price > trail_stop else exit_price
    if side == "short":
        trail_stop = low * (1 + trail_pct)
        return trail_stop if exit_price < trail_stop else exit_price
    raise ValueError("side must be 'long' or 'short'")


@dataclass
class BacktestEngine:
    """Iterate over trades applying dynamic risk and trailing stops."""

    risk_pct: float = 0.01
    log: List[Dict[str, Any]] = field(default_factory=list, init=False)
    _win_streak: int = field(default=0, init=False)
    _loss_streak: int = field(default=0, init=False)

    def _process_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        self.risk_pct = dynamic_risk_pct(self.risk_pct, self._win_streak, self._loss_streak)

        entry = float(trade["entry"])
        exit_price = float(trade["exit"])
        side = int(trade.get("side", 1))

        exit_price = apply_trailing(
            "long" if side == 1 else "short",
            float(trade.get("high", exit_price)),
            float(trade.get("low", exit_price)),
            exit_price,
            float(trade.get("trail_pct", 0.0)),
        )

        pnl_pct = calc_pnl_pct(entry, exit_price, side, trade.get("fee_rate", 0.0))
        if pnl_pct >= 0:
            self._win_streak += 1
            self._loss_streak = 0
        else:
            self._loss_streak += 1
            self._win_streak = 0

        record = {
            "entry": entry,
            "exit": exit_price,
            "side": side,
            "pnl_pct": pnl_pct,
            "risk_pct": self.risk_pct,
            "score": trade.get("score"),
            "reasons": trade.get("reasons"),
            "quality": trade.get("quality"),
        }
        self.log.append(record)
        return record

    def run(self, trades: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.log.clear()
        self._win_streak = 0
        self._loss_streak = 0
        for tr in trades:
            self._process_trade(tr)
        return self.log


def run_backtest(
    trades: Sequence[Dict[str, Any]], *, risk_pct: float = 0.01
) -> List[Dict[str, Any]]:
    engine = BacktestEngine(risk_pct=risk_pct)
    return engine.run(trades)


# ---------------------------------------------------------------------------
# Backtest helper for the multi pair runner
# ---------------------------------------------------------------------------


def _apply_slippage(price: float, side: int, bps: float, *, is_entry: bool) -> float:
    slip = bps / 10000.0
    if side == 1:
        return price * (1 + slip) if is_entry else price * (1 - slip)
    return price * (1 - slip) if is_entry else price * (1 + slip)


def backtest_symbol(
    data: List[Dict[str, Any]],
    symbol: str,
    *,
    fee_rate: float = 0.0,
    slippage_bps: float = 0.0,
    risk_pct: float = 0.01,
    initial_equity: float = 1000.0,
    leverage: float = 1.0,
    paper_constraints: bool = True,
    seed: int | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Replay a strategy on ``data`` for a single symbol.

    ``data`` is a list of dictionaries containing ``timestamp`` (as a
    ``datetime``), ``open``, ``high``, ``low``, ``close`` and ``volume``.
    The function returns a list of trades and the resulting equity curve.
    """

    if seed is not None:
        random.seed(seed)

    MIN_VOL = 0.001
    VOL_UNIT = 0.0001
    MIN_TRADE_USDT = 5.0

    equity = float(initial_equity)
    trades: List[Dict[str, Any]] = []
    equity_curve: List[Dict[str, Any]] = []
    position: Dict[str, Any] | None = None

    for i, row in enumerate(data):
        price = float(row["close"])
        ts: datetime = row["timestamp"]

        if position is not None:
            side = position["side"]
            exit_price = None
            reason = ""
            if side == 1:
                if row["low"] <= position["sl"]:
                    exit_price = position["sl"]
                    reason = "sl"
                elif row["high"] >= position["tp"]:
                    exit_price = position["tp"]
                    reason = "tp"
            else:
                if row["high"] >= position["sl"]:
                    exit_price = position["sl"]
                    reason = "sl"
                elif row["low"] <= position["tp"]:
                    exit_price = position["tp"]
                    reason = "tp"
            if exit_price is not None:
                exit_price = _apply_slippage(exit_price, -side, slippage_bps, is_entry=False)
                pnl_pct = calc_pnl_pct(position["entry"], exit_price, side, fee_rate)
                pnl_usdt = position["notional"] * (pnl_pct / 100.0)
                equity += pnl_usdt
                trades.append(
                    {
                        "entry_time": position["entry_time"],
                        "exit_time": ts,
                        "symbol": symbol,
                        "side": "long" if side == 1 else "short",
                        "entry": position["entry"],
                        "exit": exit_price,
                        "qty": position["qty"],
                        "pnl_pct": pnl_pct,
                        "pnl_usdt": pnl_usdt,
                        "fee_pct": fee_rate * 2 * 100.0,
                        "slippage_bps": slippage_bps,
                        "reason": reason,
                        "score": position.get("score"),
                        "notional": position["notional"],
                        "holding_s": (ts - position["entry_time"]).total_seconds(),
                    }
                )
                equity_curve.append({"timestamp": ts, "equity": equity})
                position = None
                continue

        ohlcv = {
            "open": [r["open"] for r in data[: i + 1]],
            "high": [r["high"] for r in data[: i + 1]],
            "low": [r["low"] for r in data[: i + 1]],
            "close": [r["close"] for r in data[: i + 1]],
            "volume": [r["volume"] for r in data[: i + 1]],
        }
        sig = generate_signal(symbol, ohlcv, equity=equity, risk_pct=risk_pct)
        if sig is None or position is not None:
            continue
        side = 1 if sig.side == "long" else -1
        entry = _apply_slippage(price, side, slippage_bps, is_entry=True)
        sl = float(sig.sl)
        tp = float(sig.tp1 or sig.tp2 or price)
        qty = float(getattr(sig, "qty", 0) or 0)
        if qty <= 0:
            dist = abs(entry - sl)
            qty = (equity * risk_pct) / dist if dist else 0.0
        if paper_constraints:
            if qty < MIN_VOL:
                qty = MIN_VOL
            qty = math.floor(qty / VOL_UNIT) * VOL_UNIT
            if qty * entry < MIN_TRADE_USDT:
                continue
        notional = qty * entry * leverage
        position = {
            "side": side,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "qty": qty,
            "entry_time": ts,
            "notional": notional,
            "score": getattr(sig, "score", None),
        }

    if position is not None:
        final_price = float(data[-1]["close"])
        ts = data[-1]["timestamp"]
        exit_price = _apply_slippage(final_price, -position["side"], slippage_bps, is_entry=False)
        pnl_pct = calc_pnl_pct(position["entry"], exit_price, position["side"], fee_rate)
        pnl_usdt = position["notional"] * (pnl_pct / 100.0)
        equity += pnl_usdt
        trades.append(
            {
                "entry_time": position["entry_time"],
                "exit_time": ts,
                "symbol": symbol,
                "side": "long" if position["side"] == 1 else "short",
                "entry": position["entry"],
                "exit": exit_price,
                "qty": position["qty"],
                "pnl_pct": pnl_pct,
                "pnl_usdt": pnl_usdt,
                "fee_pct": fee_rate * 2 * 100.0,
                "slippage_bps": slippage_bps,
                "reason": "close",
                "score": position.get("score"),
                "notional": position["notional"],
                "holding_s": (ts - position["entry_time"]).total_seconds(),
            }
        )
        equity_curve.append({"timestamp": ts, "equity": equity})

    return trades, equity_curve
