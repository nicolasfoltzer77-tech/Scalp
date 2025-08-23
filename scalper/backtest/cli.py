import argparse, asyncio, os, datetime as dt
from .runner import BacktestRunner

def parse_ts(s: str) -> int:
    d = dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp()*1000)

# Exemple de loader sync à remplacer par ton vrai fetch
def fetch_ohlcv_sync(symbol: str, timeframe: str, start_ms: int, end_ms: int):
    raise NotImplementedError("Brancher fetch_ohlcv_sync(...) sur tes données historiques")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--symbols", required=True)
    ap.add_argument("--timeframes", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--out", default="out_backtest")
    ap.add_argument("--cash", type=float, default=10000.0)
    ap.add_argument("--risk", type=float, default=0.5)
    ap.add_argument("--conc", type=int, default=4)
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    tfs = [s.strip() for s in args.timeframes.split(",")]
    start_ms, end_ms = parse_ts(args.start), parse_ts(args.end)

    runner = BacktestRunner(fetch_ohlcv_sync, args.out, args.strategy, cfg={}, cash=args.cash, risk_pct=args.risk, max_conc=args.conc)
    res = asyncio.run(runner.run_all(symbols, tfs, start_ms, end_ms))
    print("== Résumé ==")
    for sym, best in res["proposal"]["per_symbol_best"].items():
        print(f"{sym}: {best['timeframe']}  score={best['score']:.3f}  PF={best['pf']:.2f}  WR={best['winrate']:.1%}  DD={best['maxdd']:.1%}")

if __name__ == "__main__":
    main()