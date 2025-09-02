#!/usr/bin/env python3
from engine.loop_adapter import process_selection_tick
def main():
    process_selection_tick(
        symbol="BTCUSDT", last_price=60000.0, atr=120.0,
        allow_long=True, allow_short=False,
        selection_metrics={"ema_fast":60100,"ema_slow":60050,"ema_long":59500,
                           "macd_hist":0.9,"rsi":62,"adx":24,"obv_slope":0.35,
                           "vol_atr_pct":120/60000},
        bars_1s=None, notes="sample"
    )
    print("Signal écrit. Ouvre /api/signals ou le Dashboard.")
if __name__ == "__main__": main()
