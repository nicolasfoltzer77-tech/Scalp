#!/usr/bin/env python3
from __future__ import annotations
import argparse, uuid
from pathlib import Path
from engine.strategy_loader import load_strategy
from engine.signal_engine import SignalEngine
from engine.position_tracker import PositionTracker

def main():
    ap = argparse.ArgumentParser(description="Génère un signal et journalise (option ouverture simulée).")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--score", type=float, required=True, help="score [0..1]")
    ap.add_argument("--profile", default="modéré", choices=["conservateur","modéré","agressif"])
    ap.add_argument("--entry", type=float, required=True, help="prix d'entrée")
    ap.add_argument("--atr", type=float, required=True, help="ATR")
    ap.add_argument("--side-allow", default="long", choices=["long","short","both","none"])
    ap.add_argument("--open", action="store_true", help="ouvrir une position simulée si BUY/SELL")
    ap.add_argument("--qty-step", type=float, default=0.0001)
    ap.add_argument("--price-step", type=float, default=0.01)
    args = ap.parse_args()

    cfg = load_strategy(Path("config/strategy.json"))
    rprof = cfg["risk_by_profile"][args.profile]

    allow_long = args.side_allow in ("long","both")
    allow_short = args.side_allow in ("short","both")

    eng = SignalEngine()
    run_id = str(uuid.uuid4())
    sig = eng.generate_and_log_signal(
        run_id=run_id,
        symbol=args.symbol,
        strategy={"name": cfg["strategy_name"], "timeframe": "1m", "version": "1.0"},
        score=args.score,
        quality_components={"custom": args.score},
        allow_long=allow_long, allow_short=allow_short,
        profile_name=args.profile,
        buy_threshold=rprof["min_score_buy"],
        sell_threshold=rprof["min_score_sell"],
        equity=10_000.0,
        entry_price=args.entry,
        atr=args.atr,
        sl_atr_mult=cfg["entry_defaults"]["sl_atr_mult"],
        tp_r_multiple=cfg["entry_defaults"]["tp_r_multiple"],
        leverage=rprof["max_leverage"],
        risk_per_trade_pct=rprof["risk_per_trade_pct"],
        qty_step=args.qty_step,
        price_step=args.price_step,
        notes="cli",
    )

    print(f"SIGNAL {sig.side} qty={sig.qty} sl={sig.risk['sl']} tp={sig.risk['tp']}")

    if args.open and sig.side in ("BUY","SELL") and sig.qty > 0:
        tracker = PositionTracker(taker_fee_bps=int(cfg["costs"]["taker_fee_rate"]*10000))
        pos = tracker.open(
            position_id=str(uuid.uuid4()),
            symbol=args.symbol,
            side=sig.side,
            entry_price=args.entry,
            qty=sig.qty,
            leverage=sig.leverage,
            sl=sig.risk["sl"],
            tp1=sig.risk["tp"][0] if sig.risk["tp"] else None,
            tp2=sig.risk["tp"][1] if len(sig.risk["tp"])>1 else None,
            notes="cli-open",
        )
        print(f"OPENED position_id={pos.position_id}")

if __name__ == "__main__":
    main()
