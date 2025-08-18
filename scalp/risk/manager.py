"""Advanced risk management utilities.

This module provides the :class:`RiskManager` class which tracks trading
performance and adjusts risk exposure accordingly.  It also implements helper
methods for dynamic risk calculation and trailing stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from . import adjust_risk_pct


@dataclass
class RiskManager:
    """Utility class implementing kill switch, loss limits and risk scaling."""

    max_daily_loss_pct: float
    max_positions: int
    risk_pct: float
    aggressive: bool = False
    max_daily_profit_pct: Optional[float] = None
    min_risk_pct: float = 0.001
    max_risk_pct: float = 0.05

    def __post_init__(self) -> None:
        self.base_risk_pct = self.risk_pct
        self.reset_day()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    def reset_day(self) -> None:
        """Reset daily counters at the start of a new session."""
        self.daily_pnl_pct = 0.0
        self.consecutive_losses = 0
        self.win_streak = 0
        self.loss_streak = 0
        self.kill_switch = False
        self.risk_pct = self.base_risk_pct

    # ------------------------------------------------------------------
    # Trade handling
    # ------------------------------------------------------------------
    def register_trade(self, pnl_pct: float) -> None:
        """Register the outcome of a closed trade.

        The method updates win/loss streaks, daily profit and loss counters and
        adjusts the internal risk percentage.  When the daily loss or profit
        thresholds are breached the ``kill_switch`` flag is activated.
        """
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.loss_streak += 1
            self.win_streak = 0
        else:
            self.consecutive_losses = 0
            self.win_streak += 1
            self.loss_streak = 0

        self.daily_pnl_pct += pnl_pct

        if self.daily_pnl_pct <= -self.max_daily_loss_pct:
            self.kill_switch = True
        if (
            self.max_daily_profit_pct is not None
            and self.daily_pnl_pct >= self.max_daily_profit_pct
        ):
            self.kill_switch = True

        # Update risk percentage based purely on streaks for the next trade
        self.risk_pct = adjust_risk_pct(
            self.risk_pct, self.win_streak, self.loss_streak
        )

    # Backwards compatibility with older API
    record_trade = register_trade

    # ------------------------------------------------------------------
    # Dynamic risk and trailing stop utilities
    # ------------------------------------------------------------------
    def dynamic_risk_pct(self, signal_quality: float, score: float) -> float:
        """Return a risk percentage adjusted for streaks and signal quality.

        ``signal_quality`` is expected to be in the ``[0, 1]`` range where higher
        values indicate better confidence.  ``score`` acts as a modifier in the
        ``[-1, 1]`` range and allows callers to further tweak the risk based on
        arbitrary logic.  The result is clamped between ``min_risk_pct`` and
        ``max_risk_pct`` and stored in :attr:`risk_pct` for convenience.
        """
        base = adjust_risk_pct(self.base_risk_pct, self.win_streak, self.loss_streak)
        quality = max(0.0, min(1.0, signal_quality))
        score = max(-1.0, min(1.0, score))
        pct = base * (1.0 + quality * score)
        pct = max(self.min_risk_pct, min(self.max_risk_pct, pct))
        self.risk_pct = pct
        return pct

    def apply_trailing(
        self,
        direction: int,
        price: float,
        sl: float,
        atr: float,
        params: Dict[str, float],
    ) -> float:
        """Return a new stop-loss based on trailing stop parameters.

        Parameters
        ----------
        direction:
            ``1`` for long positions and ``-1`` for short positions.
        price:
            Current market price.
        sl:
            Existing stop-loss level.
        atr:
            Current Average True Range value.
        params:
            Dictionary controlling the behaviour.  Supported keys are:
            ``type`` (``"atr"`` or ``"vwap"``).  For ``atr`` trailing the key
            ``atr_mult`` (or ``mult``) specifies the ATR multiplier.  For VWAP
            trailing provide ``vwap`` and optional ``buffer``.
        """
        method = params.get("type", "atr")
        new_sl = sl
        if method == "atr":
            mult = float(params.get("atr_mult", params.get("mult", 1.0)))
            if atr > 0 and mult > 0:
                distance = atr * mult
                if direction > 0:
                    candidate = price - distance
                    if candidate > sl:
                        new_sl = candidate
                else:
                    candidate = price + distance
                    if candidate < sl:
                        new_sl = candidate
        elif method == "vwap":
            vwap_val = params.get("vwap")
            if vwap_val is not None:
                buffer = float(params.get("buffer", 0.0))
                if direction > 0:
                    candidate = vwap_val - buffer
                    if candidate > sl:
                        new_sl = candidate
                else:
                    candidate = vwap_val + buffer
                    if candidate < sl:
                        new_sl = candidate
        return new_sl

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def pause_duration(self) -> int:
        """Return seconds to pause after consecutive losses."""
        if self.consecutive_losses >= 5:
            return 60 * 60
        if self.consecutive_losses >= 3:
            return 15 * 60
        return 0

    def can_open(self, current_positions: int) -> bool:
        """Return whether a new position can be opened."""
        return (not self.kill_switch) and current_positions < self.max_positions
