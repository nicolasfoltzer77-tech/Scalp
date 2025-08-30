# -*- coding: utf-8 -*-
import json, os
from pathlib import Path
from engine.strategies.runner import load_strategies, evaluate_for

def first_symbol(reports="/opt/scalp/reports/watchlist.json"):
    p = Path(reports)
    if p.exists():
        try:
            o = json.loads(p.read_text(encoding="utf-8"))
            syms = [s for s in o.get("symbols", []) if isinstance(s, str)]
            if syms: return syms[0]
        except Exception:
            pass
    return "BTCUSDT"

if __name__ == "__main__":
    sy = first_symbol()
    cfg = load_strategies()
    comb, details = evaluate_for(sy, cfg, data_dir="/opt/scalp/data")
    print(f"[test] {sy} -> combined={comb}")
    for k,v in details.items():
        print(f" - {k}: {v}")
