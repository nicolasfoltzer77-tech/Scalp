# engine/services/tpsl_watcher.py
from __future__ import annotations
import os, time
from dataclasses import dataclass
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter, resolve_ccxt_symbol
from engine.services.order_manager import OrderManager
from engine.services.sizer import PositionSizer  # <- utilise le module sizer

@dataclass
class TpSlPlan:
    symbol: str
    side: str
    amount: float | None
    entry_type: str = "market"
    entry_price: float | None = None
    tp_price: float | None = None
    sl_price: float | None = None
    reduce_only: bool = True
    signal_risk: str = "medium"

class TpSlWatcher:
    def __init__(self, adapter: CcxtBitgetAdapter, om: OrderManager):
        self.adapter = adapter; self.om = om

    def _last_price(self, symbol: str) -> float:
        t = self.adapter.exchange.fetch_ticker(symbol)
        return float(t.get("last") or t.get("close") or 0.0)

    def place_entry_and_tp(self, plan: TpSlPlan):
        o = self.om.place(plan.symbol, plan.side, plan.entry_type,
                          plan.amount, plan.entry_price,
                          reduce_only=False, signal_risk=plan.signal_risk)
        if plan.tp_price:
            tp_side = "sell" if plan.side == "buy" else "buy"
            print(f"[tpsl] placing TP limit reduce-only @ {plan.tp_price}")
            self.om.place(plan.symbol, tp_side, "limit",
                          plan.amount, plan.tp_price,
                          reduce_only=True, signal_risk=plan.signal_risk)
        return o

    def watch_and_stop(self, plan: TpSlPlan, *, poll_ms: int = 800, timeout_s: int = 600):
        if not plan.sl_price: return False
        print(f"[tpsl] SL watcher armed @ {plan.sl_price}")
        start = time.time(); sl_side = "sell" if plan.side == "buy" else "buy"
        while (time.time() - start) < timeout_s:
            px = self._last_price(plan.symbol)
            if plan.side == "buy" and px <= plan.sl_price:
                print(f"[tpsl] SL hit: {px} <= {plan.sl_price}")
                self.om.place(plan.symbol, sl_side, "market", plan.amount,
                              reduce_only=True, signal_risk=plan.signal_risk); return True
            if plan.side == "sell" and px >= plan.sl_price:
                print(f"[tpsl] SL hit: {px} >= {plan.sl_price}")
                self.om.place(plan.symbol, sl_side, "market", plan.amount,
                              reduce_only=True, signal_risk=plan.signal_risk); return True
            time.sleep(max(0.1, poll_ms/1000))
        return False

def build_plan_from_env(adapter: CcxtBitgetAdapter) -> TpSlPlan:
    symbol = os.getenv("SYMBOL") or resolve_ccxt_symbol()
    side   = os.getenv("SIDE", "buy")

    # overrides par stratégie (optionnels)
    mode_o = os.getenv("STRAT_SIZER_MODE")
    pct_o  = os.getenv("STRAT_SIZER_PCT")
    usdt_o = os.getenv("STRAT_SIZER_USDT")
    tier_o = os.getenv("STRAT_TIER")

    if os.getenv("AMOUNT"):
        amount = float(os.getenv("AMOUNT"))
    else:
        sizer = PositionSizer(adapter)
        if any([mode_o, pct_o, usdt_o, tier_o]):
            amount, _ = sizer.size_with_overrides(
                symbol,
                mode=mode_o,
                pct=float(pct_o) if pct_o else None,
                usdt=float(usdt_o) if usdt_o else None,
                tier=int(tier_o) if tier_o else None,
            )
        else:
            amount, _ = sizer.size_from_config(symbol)

    tp_pct = float(os.getenv("TP_PCT", "0"))
    sl_pct = float(os.getenv("SL_PCT", "0"))
    tp_price_env = os.getenv("TP_PRICE")
    sl_price_env = os.getenv("SL_PRICE")

    last_px = None
    if (tp_pct and not tp_price_env) or (sl_pct and not sl_price_env):
        t = adapter.exchange.fetch_ticker(symbol); last_px = float(t.get("last") or t.get("close") or 0.0)

    tp_price = float(tp_price_env) if tp_price_env else (last_px*(1+tp_pct/100.0) if tp_pct and last_px else None)
    sl_price = float(sl_price_env) if sl_price_env else (last_px*(1-sl_pct/100.0) if sl_pct and last_px else None)

    print(f"[tpsl] plan computed: amount={amount}, tp={tp_price}, sl={sl_price}")
    return TpSlPlan(symbol=symbol, side=side, amount=amount,
                    entry_type=os.getenv("ENTRY_TYPE", "market"),
                    entry_price=float(os.getenv("ENTRY_PRICE")) if os.getenv("ENTRY_PRICE") else None,
                    tp_price=tp_price, sl_price=sl_price,
                    reduce_only=True, signal_risk=os.getenv("SIGNAL_RISK","medium"))
