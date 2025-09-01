from __future__ import annotations
import os
from dataclasses import dataclass
from engine.exchanges.ccxt_bitget import resolve_ccxt_symbol, make_exchange_from_env
from engine.services.order_manager import OrderManager


@dataclass
class TpSlPlan:
    symbol: str
    side: str
    entry_type: str
    amount: float
    price: float
    tp: float
    sl: float


class TpSlWatcher:
    def __init__(self, exchange=None):
        self.exchange = exchange or make_exchange_from_env()
        self.om = OrderManager(self.exchange)

    def _pct(self, name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except Exception:
            return default

    def build_plan_from_env(self) -> TpSlPlan:
        sym = resolve_ccxt_symbol(os.getenv("SYMBOL", "XRP/USDT:USDT"))
        side = os.getenv("SIDE", "buy").lower()
        entry_type = os.getenv("ENTRY_TYPE", "market").lower()

        last = float(self.exchange.fetch_ticker(sym)["last"])
        px = float(os.getenv("ENTRY_PX", str(last)))

        print(f"[DEBUG][Plan] symbol={sym} side={side} entry_type={entry_type} last={last} px={px}")

        mode = os.getenv("STRAT_SIZER_MODE", "usdt")
        s_usdt = os.getenv("STRAT_SIZER_USDT")
        s_pct = os.getenv("STRAT_SIZER_PCT")
        amount, px_used = self.om.sizer.compute_amount(
            sym,
            px,
            side,
            mode=mode,
            usdt=float(s_usdt) if s_usdt else None,
            pct=float(s_pct) if s_pct else None,
        )

        tp_pct = self._pct("TP_PCT", 0.3) / 100.0
        sl_pct = self._pct("SL_PCT", 0.2) / 100.0
        tp = px_used * (1 + tp_pct if side == "buy" else 1 - tp_pct)
        sl = px_used * (1 - sl_pct if side == "buy" else 1 + sl_pct)

        print(f"[DEBUG][Plan] amount={amount} px_used={px_used} tp={tp} sl={sl}")

        return TpSlPlan(sym, side, entry_type, amount, px_used, tp, sl)

    def place_entry_and_tp(self, plan: TpSlPlan):
        print(f"[DEBUG][OrderFlow] entry -> {plan}")
        entry = self.om.place(plan.symbol, plan.side, plan.entry_type, plan.amount, plan.price)

        print(f"[DEBUG][OrderFlow] placing TP={plan.tp}")
        self.om.place_tp(plan.symbol, plan.side, plan.tp, plan.amount)

        print(f"[DEBUG][OrderFlow] placing SL={plan.sl}")
        self.om.place_sl_market(plan.symbol, plan.side, plan.amount)

        return entry
