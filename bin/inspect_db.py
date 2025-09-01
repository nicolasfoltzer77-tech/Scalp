#!/usr/bin/env python3
from __future__ import annotations
from engine.storage.db import make_sqlite_engine, make_session
from engine.storage.models import Base, Order, Trade, Position

def main():
    engine = make_sqlite_engine("var/trading.db")
    Base.metadata.create_all(engine)
    s = make_session(engine)

    print("\n== ORDERS ==")
    for o in s.query(Order).order_by(Order.id.desc()).limit(20):
        print(dict(id=o.id, ex_id=o.exchange_order_id, symbol=o.symbol, side=o.side,
                   type=o.type, filled=float(o.filled or 0), avg=float(o.avg_price or 0),
                   status=str(o.status), reduce_only=o.reduce_only))

    print("\n== TRADES ==")
    for t in s.query(Trade).order_by(Trade.id.desc()).limit(20):
        print(dict(id=t.id, ex_tid=t.exchange_trade_id, symbol=t.symbol, side=t.side,
                   amount=float(t.amount), price=float(t.price), fee=float(t.fee_cost or 0)))

    print("\n== POSITIONS ==")
    for p in s.query(Position).order_by(Position.symbol):
        print(dict(symbol=p.symbol, qty=float(p.qty), entry=float(p.entry_price), realized=float(p.realized_pnl)))

if __name__ == "__main__":
    main()
