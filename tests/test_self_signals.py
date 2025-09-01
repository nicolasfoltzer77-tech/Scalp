# tests/test_self_signals.py
"""
Self-test pour la couche 2 (SignalEngine + PositionTracker).
À lancer avec :
    pytest -s tests/test_self_signals.py
ou simplement :
    python3 tests/test_self_signals.py
"""

from __future__ import annotations
from pathlib import Path
import uuid, random, sys
from datetime import datetime, timezone

from engine.strategy_loader import load_strategy
from engine.signals import SignalEngine
from engine.positions import PositionTracker

DAY = datetime.now(timezone.utc).strftime("%Y%m%d")

def get_price_atr(symbol: str) -> tuple[float, float]:
    random.seed(hash(symbol) % 10_000)
    base = {"BTCUSDT": 60000, "ETHUSDT": 2500, "SOLUSDT": 150}.get(symbol, 100)
    price = base + random.uniform(-0.5, 0.5) * base * 0.001
    atr = max(0.001 * base, 0.5)
    return round(price, 2), round(atr, 2)

def run_selftest() -> bool:
    # Prépare dossiers
    for sub in ["signals", "positions", "trades", "reports"]:
        (Path("var") / sub / DAY).mkdir(parents=True, exist_ok=True)

    cfg = load_strategy(Path("config/strategy.json"))
    run_id = str(uuid.uuid4())
    profile = "modéré"
    rprof = cfg["risk_by_profile"][profile]

    sig_engine = SignalEngine()
    tracker = PositionTracker(taker_fee_bps=int(cfg["costs"]["taker_fee_rate"] * 10000))

    universe = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    results = []

    for symbol in universe:
        entry, atr = get_price_atr(symbol)

        if symbol == "BTCUSDT":
            score = max(rprof["min_score_buy"], 0.62)  # BUY attendu
            allow_long, allow_short = True, False
        elif symbol == "ETHUSDT":
            score = 0.45  # HOLD
            allow_long, allow_short = True, True
        else:  # SOLUSDT
            score = max(rprof["min_score_sell"], 0.65)  # SELL attendu
            allow_long, allow_short = False, True

        sig = sig_engine.generate_and_log_signal(
            run_id=run_id,
            symbol=symbol,
            strategy={"name": cfg["strategy_name"], "timeframe": "1m", "version": "1.0"},
            score=score,
            quality_components={"rsi": 0.7, "trend": 0.65},
            allow_long=allow_long, allow_short=allow_short,
            profile_name=profile,
            buy_threshold=rprof["min_score_buy"],
            sell_threshold=rprof["min_score_sell"],
            equity=10_000.0,
            entry_price=entry,
            atr=atr,
            sl_atr_mult=cfg["entry_defaults"]["sl_atr_mult"],
            tp_r_multiple=cfg["entry_defaults"]["tp_r_multiple"],
            leverage=rprof["max_leverage"],
            risk_per_trade_pct=rprof["risk_per_trade_pct"],
            qty_step=0.0001,
            price_step=0.01,
            notes="self-test",
        )
        results.append(sig)

    opened = []
    for sig in results:
        if sig.side == "HOLD" or sig.qty <= 0:
            continue
        pos = tracker.open(
            position_id=str(uuid.uuid4()),
            symbol=sig.symbol,
            side=sig.side,
            entry_price=sig.entry["price_ref"],
            qty=sig.qty,
            leverage=sig.leverage,
            sl=sig.risk["sl"],
            tp1=sig.risk["tp"][0] if sig.risk["tp"] else None,
            tp2=sig.risk["tp"][1] if len(sig.risk["tp"]) > 1 else None,
            notes="self-test open",
        )
        opened.append((sig, pos))

    for sig, pos in opened:
        entry = pos.entry_price
        sl = pos.sl
        R = abs(entry - sl)
        if pos.side == "LONG":
            close_price = entry + 1.5 * R
            side = "LONG"
        else:
            close_price = entry - 1.0 * R
            side = "SHORT"
        tracker.close(
            position_id=pos.position_id,
            entry_price=entry,
            close_price=round(close_price, 2),
            qty=pos.qty,
            side=side,
        )

    sig_path = Path("var") / "signals" / DAY / "signals.jsonl"
    pos_path = Path("var") / "positions" / DAY / "positions.jsonl"
    trd_path = Path("var") / "trades" / DAY / "trades.jsonl"
    return all(p.exists() and p.stat().st_size > 0 for p in [sig_path, pos_path, trd_path])

if __name__ == "__main__":
    ok = run_selftest()
    print("Self-test OK" if ok else "Self-test ÉCHEC")
    sys.exit(0 if ok else 1)
