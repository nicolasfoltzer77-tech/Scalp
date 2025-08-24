class DataFetcher:
    def __init__(self, client):
        self.client = client

    def ohlcv_dict(self, rows):
        cols = ("timestamp", "open", "high", "low", "close", "volume")
        return {c: [float(r[i]) for r in rows] for i, c in enumerate(cols)}

    def fetch(self, symbol: str, timeframe: str, limit: int = 1500):
        rows = self.client.get_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        return self.ohlcv_dict(rows)