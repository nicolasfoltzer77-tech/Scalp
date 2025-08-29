from engine.adapters.bitget import BitgetClient

if __name__ == "__main__":
    c = BitgetClient(market="umcbl")
    rows = c.fetch_ohlcv("BTCUSDT", "1m", limit=5)
    print("rows:", len(rows))
    print("first:", rows[0])
    print("last :", rows[-1])
