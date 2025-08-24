from scalper.strategy.factory import resolve_signal_fn

class JobRunner:
    def __init__(self, strategies_cfg, equity: float, risk_pct: float):
        self.cfg = strategies_cfg
        self.equity = equity
        self.risk = risk_pct

    def run_once(self, symbol: str, timeframe: str, data: dict, data_1h: dict | None):
        fn = resolve_signal_fn(symbol, timeframe, self.cfg)
        sig = fn(symbol=symbol, timeframe=timeframe, ohlcv=data,
                 equity=self.equity, risk_pct=self.risk, ohlcv_1h=data_1h)
        return sig