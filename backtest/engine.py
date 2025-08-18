"""Simple backtest engine with dynamic risk and trailing stops.

This module provides a lightweight framework to replay trades while
tracking risk exposure.  The engine supports adaptive risk sizing via
:func:`dynamic_risk_pct` and trailing stop losses through
:func:`apply_trailing`.  A trade log is produced which includes extra
informative fields such as ``score``, ``reasons`` and ``quality``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from scalp.metrics import calc_pnl_pct
from scalp.risk import adjust_risk_pct

__all__ = [
    "dynamic_risk_pct",
    "apply_trailing",
    "BacktestEngine",
    "run_backtest",
]


def dynamic_risk_pct(risk_pct: float, win_streak: int, loss_streak: int) -> float:
    """Return a risk percentage adjusted by recent performance.

    Parameters
    ----------
    risk_pct:
        Current fraction of equity risked per trade.
    win_streak / loss_streak:
        Number of consecutive winning or losing trades.

    Returns
    -------
    float
        The new risk percentage bounded by the constraints defined in
        :func:`scalp.risk.adjust_risk_pct`.
    """

    return adjust_risk_pct(risk_pct, win_streak, loss_streak)


def apply_trailing(
    side: str,
    high: float,
    low: float,
    exit_price: float,
    trail_pct: float,
) -> float:
    """Apply a trailing stop to an exit price.

    The function emulates a basic trailing stop mechanism.  ``high`` and
    ``low`` represent the extreme prices reached while the trade was open.
    ``trail_pct`` is the trailing distance expressed as a fraction (e.g.
    ``0.01`` for 1%).  When the trailing stop is hit before the provided
    ``exit_price`` the returned value reflects the stop level instead of the
    original exit.

    Parameters
    ----------
    side: str
        ``"long"`` or ``"short"``.
    high / low: float
        Highest and lowest prices observed during the trade's lifetime.
    exit_price: float
        Intended exit price without considering trailing stops.
    trail_pct: float
        Trailing distance as a fraction.  ``0`` disables trailing.
    """

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
        """Process a single trade dictionary.

        The input must at least provide ``entry``, ``exit`` and ``side``.  It
        may also include ``high``, ``low``, ``trail_pct`` and the extra logging
        fields ``score``, ``reasons`` and ``quality``.
        """

        # Dynamically adjust the risk percentage based on performance.
        self.risk_pct = dynamic_risk_pct(self.risk_pct, self._win_streak, self._loss_streak)

        entry = float(trade["entry"])
        exit_price = float(trade["exit"])
        side = int(trade.get("side", 1))

        # Apply optional trailing stop
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
        """Run the engine on a sequence of trades.

        Parameters
        ----------
        trades:
            Iterable of trade dictionaries.  See :meth:`_process_trade` for the
            expected keys.
        """

        self.log.clear()
        self._win_streak = 0
        self._loss_streak = 0
        for tr in trades:
            self._process_trade(tr)
        return self.log


def run_backtest(
    trades: Sequence[Dict[str, Any]], *, risk_pct: float = 0.01
) -> List[Dict[str, Any]]:
    """Convenience function to execute a backtest in one call."""

    engine = BacktestEngine(risk_pct=risk_pct)
    return engine.run(trades)
