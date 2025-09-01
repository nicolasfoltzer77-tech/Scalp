# engine/services/risk_engine.py
from __future__ import annotations

import os
from typing import Optional

from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter, resolve_ccxt_symbol


class RiskError(Exception):
    """Levée si un ordre viole les règles de risk management."""


class RiskEngine:
    """
    Valide un ordre avant envoi :
      - notional >= min (market.limits.cost.min ou MIN_NOTIONAL_USDT env, défaut 5)
      - plafond notionnel optionnel (CAP_USDT env)
      - levier max optionnel (MAX_LEVERAGE env)
      - facteur de risque selon SIGNAL_RISK (low/medium/high -> 0.5/1/2)
    """

    def __init__(self, adapter: CcxtBitgetAdapter) -> None:
        self.adapter = adapter
        self.exchange = adapter.exchange

        # bornes optionnelles via env
        self.cap_usdt: Optional[float] = _env_float("CAP_USDT")
        self.max_leverage: int = _env_int("MAX_LEVERAGE", 20)

        # min notionnel par défaut si l’exchange ne fournit pas
        self.default_min_notional: float = _env_float("MIN_NOTIONAL_USDT") or 5.0

    # ------------------------------------------------------------------ utils

    def _market_min_notional(self, symbol: str) -> float:
        """Lit le min notional depuis le marché si dispo, sinon valeur par défaut/env."""
        sym = resolve_ccxt_symbol(symbol)
        market = self.exchange.market(sym)
        try:
            m = market.get("limits", {}).get("cost", {})
            v = m.get("min")
            if v is None:
                raise KeyError
            return float(v)
        except Exception:
            return float(self.default_min_notional)

    def _risk_factor(self, signal_risk: str) -> float:
        return {"low": 0.5, "medium": 1.0, "high": 2.0}.get((signal_risk or "medium").lower(), 1.0)

    # ----------------------------------------------------------------- public

    def check_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        amount_final: float,
        price_final: Optional[float],
        signal_risk: str = "medium",
    ) -> None:
        """
        Lève RiskError si l’ordre n’est pas acceptable.
        """
        sym = resolve_ccxt_symbol(symbol)

        # prix : utilise le last s’il n’est pas donné (market order par ex.)
        price = price_final
        if price is None:
            ticker = self.exchange.fetch_ticker(sym)
            price = float(ticker["last"])

        notional = float(amount_final) * float(price)

        # seuil min dynamique
        min_notional = max(self._market_min_notional(sym), self.default_min_notional)
        # facteur de risque
        factor = self._risk_factor(signal_risk)

        # 1) min notionnel
        if notional < (min_notional * factor):
            raise RiskError(
                f"RiskEngine: notional {notional:.6f} < min {min_notional*factor:.2f} USDT "
                f"(min={min_notional:.2f}, factor={factor})"
            )

        # 2) plafond notionnel optionnel
        if self.cap_usdt is not None and notional > (self.cap_usdt * factor):
            raise RiskError(
                f"RiskEngine: notional {notional:.2f} > cap {self.cap_usdt*factor:.2f} USDT (factor={factor})"
            )

        # 3) levier max optionnel (si l’exchange expose la valeur du marché)
        try:
            market = self.exchange.market(sym)
            lev = int(market.get("leverage", self.max_leverage))
            if lev > self.max_leverage:
                raise RiskError(f"RiskEngine: leverage {lev} > MAX_LEVERAGE={self.max_leverage}")
        except RiskError:
            raise
        except Exception:
            # pas bloquant si info levier non dispo
            pass


# ----------------------------- helpers env ----------------------------------


def _env_float(name: str) -> Optional[float]:
    v = os.getenv(name)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except Exception:
        return default
