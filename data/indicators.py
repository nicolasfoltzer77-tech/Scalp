import pandas as pd

__all__ = ["compute_all"]

def compute_all(
    df: pd.DataFrame,
    *,
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    atr_period: int = 14,
    swing_lookback: int = 5,
) -> pd.DataFrame:
    """Compute common indicators and return enriched DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing at least ``open``, ``high``, ``low``, ``close`` and
        ``volume`` columns ordered chronologically.

    Returns
    -------
    pd.DataFrame
        New DataFrame with additional indicator columns.
    """

    if df.empty:
        return df.copy()

    df = df.copy()

    # --- VWAP ---------------------------------------------------------------
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vwap = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vwap"] = vwap

    # --- EMAs ---------------------------------------------------------------
    df["ema20"] = df["close"].ewm(span=ema_fast, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=ema_slow, adjust=False).mean()

    # --- RSI ----------------------------------------------------------------
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(rsi_period).mean()
    avg_loss = loss.rolling(rsi_period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    df["rsi"] = rsi.fillna(50.0)

    # --- MACD ---------------------------------------------------------------
    ema_fast_series = df["close"].ewm(span=macd_fast, adjust=False).mean()
    ema_slow_series = df["close"].ewm(span=macd_slow, adjust=False).mean()
    macd = ema_fast_series - ema_slow_series
    signal = macd.ewm(span=macd_signal, adjust=False).mean()
    df["macd"] = macd
    df["macd_signal"] = signal
    df["macd_hist"] = macd - signal

    # --- OBV ----------------------------------------------------------------
    obv = [0.0]
    closes = df["close"].tolist()
    vols = df["volume"].tolist()
    for i in range(1, len(df)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + vols[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - vols[i])
        else:
            obv.append(obv[-1])
    df["obv"] = obv

    # --- ATR ----------------------------------------------------------------
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_period).mean()

    # --- Swing highs/lows ---------------------------------------------------
    df["swing_high"] = df["high"].rolling(window=swing_lookback).max()
    df["swing_low"] = df["low"].rolling(window=swing_lookback).min()

    return df
