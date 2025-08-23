import argparse, asyncio, time, os
from typing import List
from .runner import BacktestRunner, default_loader

# Remplace ceci par ton loader réel:
# Ex: un cache parquet/csv local; ou un fetch CCXT offline
def fetch_ohlcv_sync(symbol: str, timeframe: str, start_ms: int, end_ms: int):
    # TODO: brancher sur ton loader existant
    # Format: [[ts, o,h,l,c,v], ...]
    raise NotImplementedError("Brancher fetch_ohlcv_sync(...) sur ta source d'historique.")

def parse_ts(s: str) -> int:
    # YYYY-MM-DD -> epoch ms
    import datetime as dt
    d = dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp()*1000)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--symbols", required=True, help="comma-separated (e.g. BTCUSDT,ETHUSDT)")
    ap.add_argument("--timeframes", required=True, help="comma-separated (e.g. 5m,15m,1h)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="out_backtest")
    ap.add_argument("--cash", type=float, default=10000.0)
    ap.add_argument("--risk", type=float, default=0.5)
    ap.add_argument("--conc", type=int, default=4)
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    tfs = [s.strip() for s in args.timeframes.split(",") if s.strip()]
    start_ms, end_ms = parse_ts(args.start), parse_ts(args.end)

    loader = default_loader(fetch_ohlcv_sync)
    runner = BacktestRunner(loader, args.out, args.strategy, cfg={}, cash=args.cash, risk_pct=args.risk, max_conc=args.conc)
    res = asyncio.run(runner.run_all(symbols, tfs, start_ms, end_ms))
    print("== Suggestion de timeframes par symbole ==")
    for sym, best in res["proposal"]["per_symbol_best"].items():
        print(f"{sym}: {best['timeframe']}  score={best['score']:.3f}  pf={best['pf']:.2f}  wr={best['winrate']:.2%}  maxdd={best['maxdd']:.2%}")
    print(f"Résultats détaillés dans: {os.path.abspath(args.out)}")

if __name__ == "__main__":
    main()