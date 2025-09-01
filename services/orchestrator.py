# services/orchestrator.py
from __future__ import annotations
from typing import Dict, Optional, Literal
from pathlib import Path
import uuid

from engine.app_state import AppState
from engine.strategy_loader import load_strategy
from engine.signal_engine import SignalEngine
from services.order_router import PaperOrderRouter, RealOrderRouter, BaseOrderRouter

Side = Literal["BUY","SELL","HOLD"]

class Orchestrator:
    """
    Façade : appelée par la boucle existante pour convertir un tick en signal + (éventuelle) ouverture d'ordre.
    """
    def __init__(self, cfg_path: Path = Path("config/strategy.json")):
        self.state = AppState()
        self.cfg = load_strategy(cfg_path)
        self.engine = SignalEngine()
        self._router: BaseOrderRouter = PaperOrderRouter() if self.state.mode == "paper" else RealOrderRouter()

    def reload_state(self):
        self.state = AppState()
        self._router = PaperOrderRouter() if self.state.mode == "paper" else RealOrderRouter()

    def process_tick(
        self,
        *,
        symbol: str,
        price: float,
        atr: float,
        score: float,
        allow_long: bool,
        allow_short: bool,
        quality_components: Optional[Dict[str, float]] = None,
        run_id: Optional[str] = None,
        notes: Optional[str] = None,
        equity: float = 10_000.0,
        qty_step: float = 0.0001,
        price_step: float = 0.01,
        open_if_signal: bool = True,
    ) -> Dict:
        self.reload_state()
        run_id = run_id or str(uuid.uuid4())

        profile = self.state.risk_profile
        rprof = self.cfg["risk_by_profile"][profile]

        sig = self.engine.generate_and_log_signal(
            run_id=run_id,
            symbol=symbol,
            strategy={"name": self.cfg["strategy_name"], "timeframe": "1m", "version": "1.0"},
            score=score,
            quality_components=quality_components or {"score": score},
            allow_long=allow_long, allow_short=allow_short,
            profile_name=profile,
            buy_threshold=rprof["min_score_buy"],
            sell_threshold=rprof["min_score_sell"],
            equity=equity,
            entry_price=price,
            atr=atr,
            sl_atr_mult=self.cfg["entry_defaults"]["sl_atr_mult"],
            tp_r_multiple=self.cfg["entry_defaults"]["tp_r_multiple"],
            leverage=rprof["max_leverage"],
            risk_per_trade_pct=rprof["risk_per_trade_pct"],
            qty_step=qty_step, price_step=price_step,
            notes=notes or f"mode={self.state.mode}",
        )

        order_res = None
        if open_if_signal and sig.side in ("BUY", "SELL") and sig.qty > 0:
            order_res = self._router.open(
                symbol=symbol, side=sig.side, entry_price=price, qty=sig.qty,
                leverage=sig.leverage, sl=sig.risk["sl"],
                tp1=(sig.risk["tp"][0] if sig.risk["tp"] else None),
                tp2=(sig.risk["tp"][1] if len(sig.risk["tp"]) > 1 else None),
                notes=notes
            )

        return {
            "signal": sig.__dict__ if hasattr(sig, "__dict__") else sig,
            "order": (order_res.__dict__ if order_res else None),
            "state": self.state.as_dict()
        }
