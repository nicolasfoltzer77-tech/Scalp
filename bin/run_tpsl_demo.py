#!/usr/bin/env python3
from __future__ import annotations
import os
from engine.storage.db import make_sqlite_engine, make_session
from engine.storage.models import Base
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter
from engine.services.order_manager import OrderManager
from engine.services.tpsl_watcher import TpSlWatcher, build_plan_from_env

def main():
    os.makedirs("var", exist_ok=True)
    engine = make_sqlite_engine("var/trading.db")
    Base.metadata.create_all(engine)
    db = make_session(engine)

    adapter = CcxtBitgetAdapter(
        sandbox=os.getenv("BITGET_SANDBOX","1") == "1",
        default_type=os.getenv("BITGET_DEFAULT_TYPE","swap"),
        margin_mode=os.getenv("BITGET_MARGIN_MODE","isolated"),
        position_mode_hedged=os.getenv("BITGET_HEDGED","0") == "1",
    )
    om = OrderManager(db, adapter)

    if os.getenv("DRY_RUN","1") == "1":
        print("[tpsl-demo] DRY_RUN=1 -> pas d’envoi réel."); return

    plan = build_plan_from_env(adapter)
    watcher = TpSlWatcher(adapter, om)

    entry = watcher.place_entry_and_tp(plan)
    print(f"[tpsl-demo] entry ex_id={entry.exchange_order_id}")

    hit = watcher.watch_and_stop(plan,
                                 poll_ms=int(os.getenv("POLL_MS","800")),
                                 timeout_s=int(os.getenv("TIMEOUT_S","900")))
    print(f"[tpsl-demo] SL triggered? {hit}")

if __name__ == "__main__":
    main()
