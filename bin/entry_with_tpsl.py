#!/usr/bin/env python3
from __future__ import annotations
import os
from engine.storage.db import make_sqlite_engine, make_session
from engine.storage.models import Base
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter, resolve_ccxt_symbol
from engine.services.order_manager import OrderManager

def main():
    os.makedirs("var", exist_ok=True)
    engine = make_sqlite_engine("var/trading.db")
    Base.metadata.create_all(engine)
    db = make_session(engine)
    adapter = CcxtBitgetAdapter(
        sandbox=os.getenv("BITGET_SANDBOX", "1") == "1",
        default_type=os.getenv("BITGET_DEFAULT_TYPE", "swap"),
        margin_mode=os.getenv("BITGET_MARGIN_MODE", "isolated"),
        position_mode_hedged=os.getenv("BITGET_HEDGED", "0")=="1",
    )
    om = OrderManager(db, adapter)

    symbol = os.getenv("SYMBOL") or resolve_ccxt_symbol()
    side   = os.getenv("SIDE", "buy")          # sens d'entrée
    amount = float(os.getenv("AMOUNT", "0.001"))
    tp_pct = float(os.getenv("TP_PCT", "0.3")) # +0.3% par défaut
    sl_pct = float(os.getenv("SL_PCT", "0.2")) # -0.2% par défaut

    dry = os.getenv("DRY_RUN", "1") == "1"
    print(f"[tpsl] symbol={symbol} side={side} amount={amount} tp_pct={tp_pct}% sl_pct={sl_pct}% dry={dry}")
    if dry:
        print("[tpsl] DRY_RUN=1 -> pas d’envoi.")
        return

    # 1) entrée market
    entry = om.place(symbol, side, "market", amount)

    # prix de référence
    ticker = adapter.exchange.fetch_ticker(symbol)
    px = float(ticker.get("last") or ticker.get("close"))
    tp_price = px * (1 + (tp_pct/100.0)) if side=="buy" else px * (1 - (tp_pct/100.0))

    # 2) TP limit (reduce-only)
    tp_side = "sell" if side=="buy" else "buy"
    om.place(symbol, tp_side, "limit", amount, price=tp_price, reduce_only=True)

    # 3) SL market (reduce-only)
    # NB: ici on envoie un market immédiat… pour un vrai SL déclenchable,
    # il faut surveiller le prix côté moteur et déclencher quand on franchit le seuil.
    # En version simplifiée, on illustre l'appel reduce-only:
    # (si tu veux un vrai trigger, je te fournis un watcher de prix)
    print("[tpsl] TP placé, SL ‘virtuel’ à surveiller côté moteur.")

if __name__ == "__main__":
    main()
