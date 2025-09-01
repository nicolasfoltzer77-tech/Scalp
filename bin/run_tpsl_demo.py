#!/usr/bin/env python3
import json
from engine.services.tpsl_watcher import TpslWatcher, build_plan_from_env
from engine.exchanges.ccxt_bitget import CcxtBitgetAdapter

def main():
    adapter = CcxtBitgetAdapter()
    watcher = TpslWatcher(adapter)
    plan = build_plan_from_env()

    entry = watcher.place_entry_and_tp(plan)

    # CCXT retourne un dict → affichage robuste
    if isinstance(entry, dict):
        print("[tpsl-demo] entry:", json.dumps(entry, ensure_ascii=False))
    else:
        print("[tpsl-demo] entry_obj:", entry)

if __name__ == "__main__":
    main()
