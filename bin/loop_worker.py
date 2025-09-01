#!/usr/bin/env python3
from __future__ import annotations
import argparse, time, uuid, random, json
from pathlib import Path
from datetime import datetime, timezone

# Imports couche 2
from engine.strategy_loader import load_strategy
from engine.signal_engine import SignalEngine
from engine.position_tracker import PositionTracker

DAY = datetime.now(timezone.utc).strftime("%Y%m%d")

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def get_price_atr_mock(symbol: str) -> tuple[float, float]:
    """
    Placeholder prix/ATR — à remplacer par ton provider.
    """
    base = {"BTCUSDT": 60000, "ETHUSDT": 2500, "SOLUSDT": 150, "BNBUSDT": 580, "XRPUSDT": 0.55, "ADAUSDT": 0.42}.get(symbol, 100.0)
    price = base * (1.0 + random.uniform(-0.001, 0.001))  # ±0.1%
    atr = max(0.0015 * base, 0.05)  # ATR ~0.15%
    return round(price, 4), round(atr, 4)

def maybe_close_positions(current_price: float) -> None:
    """
    Logique de clôture simple: SL/TP niveau 1.
    """
    from engine.position_tracker import PositionTracker  # import local
    tracker = PositionTracker()
    pos_path = Path("var") / "positions" / DAY / "positions.jsonl"
    if not pos_path.exists():
        return
    # On lit seulement les positions encore "OPEN" dans le fichier (append only)
    opens = []
    with pos_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                evt = json.loads(line)
            except Exception:
                continue
            if isinstance(evt, dict) and evt.get("status") == "OPEN":
                opens.append(evt)
    for pos in opens:
        side = pos["side"]
        sl = pos["sl"]
        tp1 = pos.get("tp1")
        entry = pos["entry_price"]
        qty = pos["qty"]
        if side == "LONG":
            if current_price <= sl or (tp1 and current_price >= tp1):
                tracker.close(position_id=pos["position_id"], entry_price=entry, close_price=current_price, qty=qty, side=side)
        else:  # SHORT
            if current_price >= sl or (tp1 and current_price <= tp1):
                tracker.close(position_id=pos["position_id"], entry_price=entry, close_price=current_price, qty=qty, side=side)

def main():
    ap = argparse.ArgumentParser(description="Boucle generation signaux + ouverture/fermeture simulée.")
    ap.add_argument("--profile", default="modéré", choices=["conservateur","modéré","agressif"])
    ap.add_argument("--interval-sec", type=float, default=None, help="Override de l'intervalle en secondes (sinon calculé par profil)")
    ap.add_argument("--duration-min", type=float, default=0, help="Durée de run (0 = infini)")
    ap.add_argument("--symbols", nargs="*", default=None, help="Liste de symboles (défaut = assets de la stratégie)")
    ap.add_argument("--open", action="store_true", help="Ouvrir une position simulée pour BUY/SELL")
    args = ap.parse_args()

    cfg = load_strategy(Path("config/strategy.json"))
    assets = args.symbols or cfg["raw"].get("assets", ["BTCUSDT","ETHUSDT"])
    rprof = cfg["risk_by_profile"][args.profile]

    # Fréquence par profil (ajustable)
    base_interval = {"conservateur": 60.0, "modéré": 30.0, "agressif": 10.0}[args.profile]
    interval = float(args.interval_sec or base_interval)

    sig_engine = SignalEngine()
    tracker = PositionTracker(taker_fee_bps=int(cfg["costs"]["taker_fee_rate"]*10000))
    run_id = str(uuid.uuid4())

    print(f"[{utcnow()}] loop start profile={args.profile} interval={interval}s assets={assets}")

    deadline = time.time() + args.duration_min*60 if args.duration_min > 0 else None
    i = 0
    while True:
        i += 1
        for symbol in assets:
            price, atr = get_price_atr_mock(symbol)

            # Ici, un vrai score doit venir de ta pipeline (regime + entry sets).
            # On simule: BTC → score plus haut une fois sur deux; autres modérés.
            base_score = 0.64 if (symbol.endswith("USDT") and (i % 2 == 1) and symbol in ("BTCUSDT","SOLUSDT")) else 0.48
            score = base_score + random.uniform(-0.03, 0.03)
            score = max(0.0, min(1.0, score))

            allow_long, allow_short = True, True  # branche demain sur regime_layer "direction"
            sig = sig_engine.generate_and_log_signal(
                run_id=run_id,
                symbol=symbol,
                strategy={"name": cfg["strategy_name"], "timeframe": "1m", "version": "1.0"},
                score=score,
                quality_components={"mock": score},
                allow_long=allow_long, allow_short=allow_short,
                profile_name=args.profile,
                buy_threshold=rprof["min_score_buy"],
                sell_threshold=rprof["min_score_sell"],
                equity=10_000.0,
                entry_price=price,
                atr=atr,
                sl_atr_mult=cfg["entry_defaults"]["sl_atr_mult"],
                tp_r_multiple=cfg["entry_defaults"]["tp_r_multiple"],
                leverage=rprof["max_leverage"],
                risk_per_trade_pct=rprof["risk_per_trade_pct"],
                qty_step=0.0001,
                price_step=0.01,
                notes="loop",
            )

            if args.open and sig.side in ("BUY","SELL") and sig.qty > 0:
                tracker.open(
                    position_id=str(uuid.uuid4()),
                    symbol=symbol,
                    side=sig.side,
                    entry_price=price,
                    qty=sig.qty,
                    leverage=sig.leverage,
                    sl=sig.risk["sl"],
                    tp1=sig.risk["tp"][0] if sig.risk["tp"] else None,
                    tp2=sig.risk["tp"][1] if len(sig.risk["tp"])>1 else None,
                    notes=f"loop {args.profile}",
                )

            # on simule un tick pour fermer si SL/TP atteint (stupid but ok for dry-run)
            drift = random.uniform(-1.0, 1.0) * atr
            current_price = round(price + drift, 4)
            maybe_close_positions(current_price)

        if deadline and time.time() >= deadline:
            print(f"[{utcnow()}] loop end (duration reached)")
            break

        time.sleep(interval)

if __name__ == "__main__":
    main()
