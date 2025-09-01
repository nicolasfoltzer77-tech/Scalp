#!/usr/bin/env python3
from __future__ import annotations
import json
from engine.services.tpsl_watcher import TpSlWatcher


def main():
    watcher = TpSlWatcher()
    plan = watcher.build_plan_from_env()
    print(f"[tpsl] plan computed: amount={plan.amount}, tp={plan.tp}, sl={plan.sl}")

    entry = watcher.place_entry_and_tp(plan)
    oid = entry.get("id") if isinstance(entry, dict) else entry
    print(f"[tpsl-demo] entry ok -> {json.dumps(entry, default=str)} (id={oid})")


if __name__ == "__main__":
    main()
