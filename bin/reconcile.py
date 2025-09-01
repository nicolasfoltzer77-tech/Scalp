#!/usr/bin/env python3
from __future__ import annotations
import os
from engine.storage.db import make_sqlite_engine, make_session
from engine.storage.models import Base
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter
from engine.services.reconciler import Reconciler

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
    Reconciler(db, adapter).run()
    print("[reconcile] done.")

if __name__ == "__main__":
    main()
