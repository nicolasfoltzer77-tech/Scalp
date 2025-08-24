# scalper/core/signal.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict, Any

Side = Literal["long", "short"]

@dataclass
class Signal:
    symbol: str
    timeframe: str
    side: Side
    entry: float
    sl: float
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    qty: Optional[float] = None
    score: float = 0.0          # 0..1 (ou entier, normalisé au besoin)
    quality: float = 0.0        # 0..1
    reasons: List[str] = field(default_factory=list)
    timestamp: Optional[int] = None  # ms epoch de la bougie de déclenchement
    extra: Dict[str, Any] = field(default_factory=dict)

    def risk_per_unit(self) -> float:
        return abs(self.entry - self.sl)

    def as_dict(self) -> Dict[str, Any]:
        d = {
            "symbol": self.symbol, "timeframe": self.timeframe, "side": self.side,
            "entry": self.entry, "sl": self.sl, "tp1": self.tp1, "tp2": self.tp2,
            "qty": self.qty, "score": self.score, "quality": self.quality,
            "timestamp": self.timestamp, "reasons": "|".join(self.reasons),
        }
        d.update(self.extra or {})
        return d