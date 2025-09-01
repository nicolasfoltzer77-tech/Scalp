# engine/signal_engine.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Dict, List, Optional, TypedDict
import json, math

Side = Literal["BUY", "SELL", "HOLD"]

class StrategyMeta(TypedDict):
    name: str
    timeframe: str
    version: str | None

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _round_step(x: float, step: float) -> float:
    if step <= 0:
        return x
    return math.floor(x / step) * step

@dataclass
class Signal:
    ts: str
    run_id: str
    symbol: str
    side: Side
    score: float
    risk_profile: str
    leverage: float
    qty: float
    entry: Dict
    risk: Dict
    quality: Dict
    strategy: StrategyMeta
    notes: Optional[str] = None

class SignalEngine:
    def __init__(self, base_dir: Path = Path("var")):
        self.base_dir = base_dir

    def _out_path(self) -> Path:
        d = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.base_dir / "signals" / d / "signals.jsonl"

    @staticmethod
    def decide_side(score: float, allow_long: bool, allow_short: bool, buy_threshold: float, sell_threshold: float) -> Side:
        if allow_long and score >= buy_threshold:
            return "BUY"
        if allow_short and score >= sell_threshold:
            return "SELL"
        return "HOLD"

    @staticmethod
    def position_size(equity: float, entry_price: float, sl_price: float, risk_per_trade_pct: float, leverage: float, qty_step: float = 1e-6) -> float:
        risk_per_unit = abs(entry_price - sl_price)
        if risk_per_unit <= 0:
            return 0.0
        capital_at_risk = equity * risk_per_trade_pct
        raw_qty = (capital_at_risk * leverage) / risk_per_unit
        return max(_round_step(raw_qty, qty_step), 0.0)

    @staticmethod
    def _tp_list(entry_price: float, sl: float, side: Side, r_mults: List[float], price_step: float) -> List[float]:
        tps = []
        for r in r_mults:
            if side == "BUY":
                tp = entry_price + r * (entry_price - sl)
            elif side == "SELL":
                tp = entry_price - r * (sl - entry_price)
            else:
                continue
            tps.append(_round_step(tp, price_step))
        return tps

    @staticmethod
    def _write_jsonl(path: Path, obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def generate_and_log_signal(
        self,
        *,
        run_id: str,
        symbol: str,
        strategy: StrategyMeta,
        score: float,
        quality_components: Dict[str, float],
        allow_long: bool,
        allow_short: bool,
        profile_name: str,
        buy_threshold: float,
        sell_threshold: float,
        equity: float,
        entry_price: float,
        atr: float,
        sl_atr_mult: float,
        tp_r_multiple: List[float],
        leverage: float,
        risk_per_trade_pct: float,
        qty_step: float = 1e-6,
        price_step: float = 0.1,
        notes: str | None = None,
    ) -> Signal:
        side = self.decide_side(score, allow_long, allow_short, buy_threshold, sell_threshold)

        if side == "BUY":
            sl = _round_step(entry_price - sl_atr_mult * atr, price_step)
        elif side == "SELL":
            sl = _round_step(entry_price + sl_atr_mult * atr, price_step)
        else:
            sl = entry_price

        tps = self._tp_list(entry_price, sl, side, tp_r_multiple, price_step)

        qty = 0.0 if side == "HOLD" else self.position_size(
            equity=equity, entry_price=entry_price, sl_price=sl,
            risk_per_trade_pct=risk_per_trade_pct, leverage=leverage, qty_step=qty_step
        )

        sig = Signal(
            ts=_utcnow(), run_id=run_id, symbol=symbol, side=side, score=score,
            risk_profile=profile_name, leverage=leverage, qty=qty,
            entry={"type": "market", "price_ref": entry_price},
            risk={"sl": sl, "tp": tps, "atr": atr, "r_multiple": tp_r_multiple, "sl_atr_mult": sl_atr_mult},
            quality={"components": quality_components, "overall": score},
            strategy=strategy, notes=notes,
        )
        self._write_jsonl(self._out_path(), asdict(sig))
        return sig
