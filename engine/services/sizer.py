# engine/services/sizer.py
from __future__ import annotations
import os
from typing import Optional, Tuple
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter

class SizerError(Exception):
    pass

class PositionSizer:
    """
    Calcule (amount, notionalUSDT) selon :
      - RISK_MODE=percent -> notional = balanceUSDT * (pct * tier_mult)/100
      - RISK_MODE=usdt    -> notional = usdt * tier_mult
    tiers: 1->0.5x, 2->1.0x, 3->1.5x
    Overrides possibles: mode, pct, usdt, tier (prioritaires sur l'env).
    """
    TIER_MULT = {1: 0.5, 2: 1.0, 3: 1.5}

    def __init__(self, adapter: CcxtBitgetAdapter):
        self.adapter = adapter

    @staticmethod
    def _envfloat(name: str) -> Optional[float]:
        v = os.getenv(name)
        try:
            return float(v) if v not in (None, "") else None
        except Exception:
            return None

    def _price(self, symbol: str) -> float:
        t = self.adapter.exchange.fetch_ticker(symbol)
        return float(t.get("last") or t.get("close") or 0.0)

    def _balance_usdt(self) -> float:
        b = self.adapter.exchange.fetch_balance()
        return float(b.get("total", {}).get("USDT", b.get("free", {}).get("USDT", 0.0)))

    def size_from_config(self, symbol: str, *, tier: int = 2) -> Tuple[float, float]:
        mode = (os.getenv("RISK_MODE") or "percent").lower()
        pct  = self._envfloat("RISK_PCT_BASE")  or 1.0
        usdt = self._envfloat("RISK_USDT_BASE") or 10.0
        tier = max(1, min(3, int(os.getenv("RISK_TIER", tier))))
        return self.size_with_overrides(symbol, mode=mode, pct=pct, usdt=usdt, tier=tier)

    def size_with_overrides(self, symbol: str,
                            *, mode: str | None = None,
                            pct: float | None = None,
                            usdt: float | None = None,
                            tier: int | None = None) -> Tuple[float, float]:
        mode = (mode or os.getenv("RISK_MODE") or "percent").lower()
        tier = max(1, min(3, int(tier if tier is not None else os.getenv("RISK_TIER", 2))))
        tier_mult = self.TIER_MULT.get(tier, 1.0)

        price = self._price(symbol)
        if price <= 0:
            raise SizerError("PositionSizer: prix indisponible")

        if mode == "percent":
            pct = float(pct if pct is not None else (self._envfloat("RISK_PCT_BASE") or 1.0))
            bal = self._balance_usdt()
            if bal <= 0:
                raise SizerError("PositionSizer: solde USDT indisponible")
            notional = bal * (pct * tier_mult) / 100.0
        elif mode == "usdt":
            usdt = float(usdt if usdt is not None else (self._envfloat("RISK_USDT_BASE") or 10.0))
            notional = usdt * tier_mult
        else:
            raise SizerError(f"PositionSizer: RISK_MODE inconnu '{mode}'")

        if notional <= 0:
            raise SizerError("PositionSizer: notional nul")

        amount = notional / price
        return amount, notional
