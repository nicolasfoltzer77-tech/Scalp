from __future__ import annotations
import pandas as pd
from .indicators import ema, atr

def compute_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    fast = int(params.get("ema_fast", 20))
    slow = int(params.get("ema_slow", 50))
    atr_n = int(params.get("atr_period", 14))
    df = df.copy()
    df["ema_fast"] = ema(df["close"], fast)
    df["ema_slow"] = ema(df["close"], slow)
    df["atr"] = atr(df, atr_n)
    # signal = +1 si croisement haussier, -1 si baissier, 0 sinon
    cond_up = (df["ema_fast"] > df["ema_slow"]) & (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
    cond_dn = (df["ema_fast"] < df["ema_slow"]) & (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))
    df["signal"] = 0
    df.loc[cond_up, "signal"] = 1
    df.loc[cond_dn, "signal"] = -1
    return df