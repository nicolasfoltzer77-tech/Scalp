import os
import time
from datetime import datetime, timezone
from engine.adapters.bitget import BitgetClient

def env(name, default=None, required=False):
    v = os.getenv(name, default)
    if required and not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def main():
    # --- config via ENV ---
    symbol = env("LIVE_SYMBOL", "BTCUSDT")
    tf     = env("LIVE_TF", "1m")
    market = env("LIVE_MARKET", "umcbl")  # futures USDT
    dry    = env("DRY_RUN", "1") in ("1","true","True","YES","yes")

    # combien de bougies pour un premier calcul
    warmup = int(env("WARMUP", "200"))
    sleep_s = 1 if tf.endswith("s") else 5   # mini pause entre pulls

    print(f"[{now_iso()}] live start  symbol={symbol} tf={tf} market={market} dry_run={dry}")

    client = BitgetClient(market=market)

    # --- warmup ---
    df = client.fetch_ohlcv_df(symbol, tf, limit=warmup)
    if df.empty:
        raise RuntimeError(f"Aucune donnée OHLCV pour {symbol} {tf} ({market})")

    def last_close(dframe):
        return float(dframe.iloc[-1]["close"])

    def simple_signal(dframe):
        # Exemple ultra simple: slope des 10 dernières closes
        w = 10 if len(dframe) >= 10 else len(dframe)
        if w < 2: 
            return 0
        s = dframe["close"].astype(float).tail(w).values
        return 1 if s[-1] > s[0]*1.0005 else (-1 if s[-1] < s[0]*0.9995 else 0)

    print(f"[{now_iso()}] warmup loaded rows={len(df)} last_close={last_close(df):.4f}")

    # --- loop ---
    while True:
        try:
            # on ne tire que quelques dernières bougies
            tail = client.fetch_ohlcv_df(symbol, tf, limit=5)
            if tail.empty:
                print(f"[{now_iso()}] ⚠ no new data")
                time.sleep(sleep_s)
                continue

            # concat pour garder un historique court
            df = df.append(tail.iloc[-1], ignore_index=True)
            if len(df) > 600:
                df = df.iloc[-600:]

            sig = simple_signal(df)
            px  = last_close(df)
            txt = "HOLD"
            if sig > 0:  txt = "BUY"
            if sig < 0:  txt = "SELL"

            print(f"[{now_iso()}] {symbol} {tf} px={px:.4f} signal={txt} (dry={dry})")

            # Ici on gérerait les ordres réels si dry=False
            # if not dry and sig != 0:
            #     client.create_order(symbol=symbol, side=("buy" if sig>0 else "sell"),
            #                         size=os.getenv("LIVE_SIZE","0.001"), type="market")

        except KeyboardInterrupt:
            print(f"[{now_iso()}] stop by user")
            break
        except Exception as e:
            print(f"[{now_iso()}] ERROR: {type(e).__name__}: {e}")
        time.sleep(sleep_s)

if __name__ == "__main__":
    main()
