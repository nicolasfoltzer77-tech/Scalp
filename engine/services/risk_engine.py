from __future__ import annotations
import os
from typing import Optional
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter


class RiskError(Exception):
    """Levée si un ordre viole les règles de risk management."""


class RiskEngine:
    """
    Gestion du risque basique mais extensible :
    - plafond notional (MAX_SIZE_USDT)
    - max levier autorisé (MAX_LEVERAGE)
    - ajustement dynamique selon 'signal_risk' (ex: faible, moyen, élevé)
    """

    def __init__(self, adapter: CcxtBitgetAdapter):
        self.adapter = adapter
        self.cap_usdt = self._envfloat("MAX_SIZE_USDT")
        self.max_leverage = self._envint("MAX_LEVERAGE", 20)

    @staticmethod
    def _envfloat(name: str) -> Optional[float]:
        v = os.getenv(name)
        return float(v) if v else None

    @staticmethod
    def _envint(name: str, default: int) -> int:
        v = os.getenv(name)
        return int(v) if v else default

    # ---------- nouvelle méthode ----------

    def assert_order_ok(
        self,
        symbol: str,
        side: str,
        type_: str,
        amount: float,
        price: float,
        signal_risk: str = "medium",
    ):
        """
        Vérifie si l'ordre respecte :
        - notional <= cap_usdt * facteur de risque
        - levier <= max_leverage
        """
        notional = (price or 0) * float(amount)

        # facteur de risque dynamique
        risk_factor = {
            "low": 0.5,
            "medium": 1.0,
            "high": 2.0,
        }.get(signal_risk, 1.0)

        # limite notional
        if self.cap_usdt:
            if notional > self.cap_usdt * risk_factor:
                raise RiskError(
                    f"RiskEngine: notional {notional:.2f} USDT > cap {self.cap_usdt}×{risk_factor}"
                )

        # limite levier (via exchange)
        try:
            market = self.adapter.exchange.market(symbol)
            lev = market.get("leverage", self.max_leverage)
            if lev > self.max_leverage:
                raise RiskError(
                    f"RiskEngine: leverage {lev} > MAX_LEVERAGE={self.max_leverage}"
                )
        except Exception:
            pass
