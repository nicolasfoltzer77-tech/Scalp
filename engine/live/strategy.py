from __future__ import annotations
import pandas as pd

class EMACross:
    """
    Mini strategy:
      - fast EMA crosses above slow EMA -> long
      - fast EMA crosses below slow EMA -> flat (close)
    No shorting for now (keeps risk simple).
    Signals: "long", "close", or None
    """

    def __init__(self, fast: int = 9, slow: int = 21):
        assert fast < slow, "fast EMA must be < slow EMA"
        self.fast = fast
        self.slow = slow
        self._prev_fast = None
        self._prev_slow = None

    def on_warmup(self, df: pd.DataFrame) -> None:
        ema_f = df["close"].ewm(span=self.fast, adjust=False).mean()
        ema_s = df["close"].ewm(span=self.slow, adjust=False).mean()
        self._prev_fast = float(ema_f.iloc[-1])
        self._prev_slow = float(ema_s.iloc[-1])

    def on_tick(self, last_closes: list[float]) -> str | None:
        """last_closes contains the most recent closes (append newest at end)."""
        if len(last_closes) < self.slow:
            return None
        s = pd.Series(last_closes)
        ema_f = float(s.ewm(span=self.fast, adjust=False).mean().iloc[-1])
        ema_s = float(s.ewm(span=self.slow, adjust=False).mean().iloc[-1])

        signal = None
        if self._prev_fast is not None and self._prev_slow is not None:
            crossed_up = self._prev_fast <= self._prev_slow and ema_f > ema_s
            crossed_dn = self._prev_fast >= self._prev_slow and ema_f < ema_s
            if crossed_up:
                signal = "long"
            elif crossed_dn:
                signal = "close"

        self._prev_fast, self._prev_slow = ema_f, ema_s
        return signal
