# engine/services/order_manager.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import math

from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter
from engine.services.risk_engine import RiskEngine, RiskError


@dataclass
class PlacedOrder:
    symbol: str
    side: str
    type: str
    amount: float
    price: Optional[float]
    reduce_only: bool
    params: Dict[str, Any]
    exchange_order_id: Optional[str] = None


class InsufficientFunds(Exception):
    """Levée si le solde USDT disponible est insuffisant pour l'ordre."""
    pass


class OrderManager:
    """
    Passage d'ordres Futures USDT (Bitget via CCXT) avec :
      - contrôles RiskEngine,
      - normalisation quantité (precision, step, min amount),
      - respect du min notionnel (5 USDT Bitget),
      - vérification solvabilité avant l'appel API,
      - support reduceOnly.
    """

    def __init__(self, db_session, adapter: CcxtBitgetAdapter):
        self.db = db_session
        self.adapter = adapter
        self.engine = RiskEngine(adapter)

    # ---------- helpers marché / balance ----------

    def _market(self, symbol: str) -> dict:
        return self.adapter.exchange.market(symbol)

    def _last_price(self, symbol: str) -> float:
        t = self.adapter.exchange.fetch_ticker(symbol)
        return float(t.get("last") or t.get("close") or 0.0)

    def _free_usdt(self) -> float:
        bal = self.adapter.exchange.fetch_balance()
        # structure CCXT standard: bal["free"]["USDT"]
        return float(bal.get("free", {}).get("USDT", 0.0))

    # ---------- utilitaires précision/step ----------

    @staticmethod
    def _round_to_precision(x: float, prec: Optional[int]) -> float:
        if prec is None:
            return x
        q = 10 ** int(prec)
        # floor pour ne pas dépasser la précision autorisée
        return math.floor(float(x) * q) / q

    @staticmethod
    def _ceil_to_step(x: float, step: Optional[float]) -> float:
        if not step:
            return x
        return math.ceil(float(x) / float(step)) * float(step)

    def _conform_amount(self, symbol: str, amount: float, price: Optional[float]) -> float:
        """
        Ajuste la quantité demandée pour respecter :
          - precision amount,
          - min amount,
          - step amount,
          - min cost (si présent),
          - min notionnel Bitget futures = 5 USDT.
        """
        mkt = self._market(symbol)
        precision = (mkt.get("precision") or {}).get("amount")
        limits = mkt.get("limits") or {}
        min_amt = (limits.get("amount") or {}).get("min")
        step_amt = (limits.get("amount") or {}).get("step")
        min_cost = (limits.get("cost") or {}).get("min")

        amt = float(amount)
        # 1) precision
        amt = self._round_to_precision(amt, precision)
        # 2) min amount
        if min_amt is not None:
            amt = max(amt, float(min_amt))
        # 3) step
        if step_amt:
            amt = self._ceil_to_step(amt, float(step_amt))
            amt = self._round_to_precision(amt, precision)

        px = float(price) if price else None
        # 4) min cost de l'exchange (si renseigné)
        if (min_cost is not None) and px:
            if amt * px < float(min_cost):
                needed = float(min_cost) / px
                amt = max(amt, needed)
                if step_amt:
                    amt = self._ceil_to_step(amt, float(step_amt))
                amt = self._round_to_precision(amt, precision)

        # 5) hard floor Bitget futures: notionnel >= 5 USDT
        if px and amt * px < 5.0:
            needed = 5.0 / px
            amt = max(amt, needed)
            if step_amt:
                amt = self._ceil_to_step(amt, float(step_amt))
            amt = self._round_to_precision(amt, precision)

        return amt

    # ---------- API publique ----------

    def place(
        self,
        symbol: str,
        side: str,
        type_: str,
        amount: float,
        price: Optional[float] = None,
        *,
        reduce_only: bool = False,
        params: Optional[Dict[str, Any]] = None,
        signal_risk: str = "medium",
    ) -> PlacedOrder:
        """
        Place un ordre après :
          - check RiskEngine (avant/après normalisation),
          - normalisation de la quantité,
          - vérification solvabilité (si non reduceOnly).
        """
        params = dict(params or {})
        # prix : pour checks & min cost (utilise ticker si non fourni)
        px = float(price) if price is not None else self._last_price(symbol)
        if px <= 0:
            raise ValueError(f"Prix indisponible pour {symbol}")

        # 1) pré-check risque sur la demande initiale
        self.engine.check_order(symbol, side, type_, amount, px, signal_risk)

        # 2) normaliser quantité (precision/step/mins/5USDT)
        amt = self._conform_amount(symbol, float(amount), px)

        # 3) check risque sur la quantité finale
        self.engine.check_order(symbol, side, type_, amt, px, signal_risk)

        # 4) solvabilité (sauf reduceOnly)
        if not reduce_only:
            need = amt * px
            free = self._free_usdt()
            if free and need > free:
                raise InsufficientFunds(
                    f"Solde USDT insuffisant : free={free:.2f} < besoin≈{need:.2f}"
                )

        # 5) reduceOnly
        if reduce_only:
            params.setdefault("reduceOnly", True)

        # 6) envoi CCXT
        order = self.adapter.create_order(
            symbol, side, type_, amt, px, reduce_only=reduce_only, params=params
        )

        ex_id = None
        try:
            ex_id = order.get("id") or order.get("orderId") or order.get("data", {}).get("orderId")
        except Exception:
            pass

        return PlacedOrder(
            symbol=symbol,
            side=side,
            type=type_,
            amount=amt,
            price=px,
            reduce_only=reduce_only,
            params=params,
            exchange_order_id=ex_id,
        )
