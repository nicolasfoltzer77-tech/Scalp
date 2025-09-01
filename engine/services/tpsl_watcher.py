# engine/services/tpsl_watcher.py
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

from engine.services.order_manager import OrderManager
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter

# ---------- Plan ----------
@dataclass
class TpSlPlan:
    symbol: str
    side: str                 # "buy" | "sell"
    entry_type: str           # "market" | "limit"
    tp_price: Optional[float] # target price (limit, reduce-only)
    sl_price: Optional[float] # stop price (best effort)
    risk_mode: str            # "percent" | "usdt"
    risk_pct_base: float
    risk_usdt_base: float
    tier: int                 # 1..3, sur-multiplicateur
    signal_risk: str          # "low"|"medium"|"high"

# ---------- Sizer basique ----------
class PositionSizer:
    """
    Calcule un montant (amount) cohérent avec le marché Bitget (via CCXT)
    et applique un notional mini (ex: 5 USDT).
    """
    def __init__(self, adapter: CcxtBitgetAdapter):
        self.adapter = adapter

    def _market_info(self, symbol: str) -> Tuple[Dict[str, Any], int, float]:
        m = self.adapter.exchange.market(symbol)
        amount_prec = int(m.get("precision", {}).get("amount", 0))  # souvent 0 ou 1 pour futures
        price_prec  = float(m.get("precision", {}).get("price", 0.0001))
        min_cost = (
            (m.get("limits", {}) or {}).get("cost", {}) or {}
        ).get("min")
        return m, amount_prec, (min_cost if min_cost is not None else float(os.getenv("MIN_NOTIONAL_USDT", "5")))

    def _last_px(self, symbol: str) -> float:
        # prix: last, fallback mid
        t = self.adapter.exchange.fetch_ticker(symbol)
        px = t.get("last") or t.get("info", {}).get("lastPr")
        if not px:
            ob = self.adapter.exchange.fetch_order_book(symbol, 5)
            bid = ob["bids"][0][0]; ask = ob["asks"][0][0]
            px = (bid + ask) / 2
        return float(px)

    def compute(self, symbol: str, side: str, risk_mode: str,
                risk_pct_base: float, risk_usdt_base: float,
                tier: int) -> Tuple[float, float]:
        """
        Retourne (amount_final arrondi, price_ref)
        """
        px = self._last_px(symbol)
        m, amount_prec, min_cost = self._market_info(symbol)

        # 1) montant de base
        mult = {1:0.5, 2:1.0, 3:1.5}.get(int(tier or 2), 1.0)
        if (risk_mode or "").lower() == "percent":
            bal = self.adapter.exchange.fetch_balance().get("USDT", {}).get("free", 0) or 0
            notional = bal * float(risk_pct_base or 1.0) * 0.01 * mult
        else:  # "usdt"
            notional = float(risk_usdt_base or 5.0) * mult

        # 2) convertir en amount et respecter min cost
        amount = notional / px if px > 0 else 0
        # arrondi "amount" (futures XRP: precision 1 => pas de décimales)
        if amount_prec >= 1:
            step = 10 ** (-amount_prec)
            amount = int(round(amount / step)) * step
        else:
            # la plupart des contrats coin-m: amount entier
            amount = int(round(amount)) or 1

        # 3) bump si notional < min
        if amount * px < min_cost:
            bump = (min_cost / px)
            amount = int(bump) if amount_prec == 0 else round(bump, amount_prec)
            if amount * px < min_cost:
                amount += 1

        return float(amount), float(px)

# ---------- Watcher ----------
class TpslWatcher:
    def __init__(self, adapter: Optional[CcxtBitgetAdapter] = None):
        self.adapter = adapter or CcxtBitgetAdapter()
        self.om = OrderManager(None, self.adapter)  # db=None dans la démo
        self.sizer = PositionSizer(self.adapter)

    def _tp_px(self, side: str, px: float, pct: float) -> float:
        pct = float(pct or 0) * 0.01
        return round(px * (1+pct if side == "buy" else 1-pct), 4)

    def _sl_px(self, side: str, px: float, pct: float) -> float:
        pct = float(pct or 0) * 0.01
        return round(px * (1-pct if side == "buy" else 1+pct), 4)

    def place_entry_and_tp(self, plan: TpSlPlan):
        # 1) sizing
        amount, px_ref = self.sizer.compute(
            plan.symbol, plan.side, plan.risk_mode,
            plan.risk_pct_base, plan.risk_usdt_base, plan.tier
        )

        # 2) ENTRY (market)
        entry = self.om.place(plan.symbol, plan.side, "market", amount, None, params={})
        # 3) TP (limit reduce-only)
        tp_side = "sell" if plan.side == "buy" else "buy"
        tp_px = plan.tp_price or self._tp_px(plan.side, px_ref, float(os.getenv("TP_PCT", "0.3")))
        self.om.place(plan.symbol, tp_side, "limit", amount, tp_px, params={"reduceOnly": True})

        # 4) SL (best effort: on affiche l’intention, la pose d’un SL conditionnel Bitget via CCXT
        #      dépend de params spécifiques; on évite de bloquer le flow ici)
        if plan.sl_price:
            try:
                sl_side = "sell" if plan.side == "buy" else "buy"
                # Certains comptes Bitget exigent un ordre conditionnel avec 'triggerPrice'
                params = {"reduceOnly": True, "stopLossPrice": plan.sl_price}
                self.om.place(plan.symbol, sl_side, "market", amount, None, params=params)
            except Exception as e:
                print(f"[tpsl] SL non posé (info) -> {e}")

        return entry

# ---------- Build plan ----------
def build_plan_from_env() -> TpSlPlan:
    side = os.getenv("SIDE", "buy").lower()
    symbol = os.getenv("SYMBOL", "XRP/USDT:USDT")

    risk_mode = os.getenv("STRAT_SIZER_MODE", os.getenv("RISK_MODE", "usdt")).lower()
    risk_pct_base = float(os.getenv("RISK_PCT_BASE", "1"))
    risk_usdt_base = float(os.getenv("STRAT_SIZER_USDT", os.getenv("RISK_USDT_BASE", "5")))
    tier = int(os.getenv("STRAT_TIER", os.getenv("RISK_TIER", "2")))
    signal_risk = os.getenv("SIGNAL_RISK", "medium")

    tp_pct = float(os.getenv("TP_PCT", "0.3"))
    sl_pct = float(os.getenv("SL_PCT", "0.2"))

    # prix de référence provisoire (sera recalculé par PositionSizer)
    # mais utile pour préremplir des valeurs si besoin
    adapter = CcxtBitgetAdapter()
    px = PositionSizer(adapter)._last_px(symbol)
    tp = round(px * (1+tp_pct/100 if side == "buy" else 1-tp_pct/100), 4)
    sl = round(px * (1-sl_pct/100 if side == "buy" else 1+sl_pct/100), 4)

    return TpSlPlan(
        symbol=symbol,
        side=side,
        entry_type="market",
        tp_price=tp,
        sl_price=sl,
        risk_mode=risk_mode,
        risk_pct_base=risk_pct_base,
        risk_usdt_base=risk_usdt_base,
        tier=tier,
        signal_risk=signal_risk,
    )
