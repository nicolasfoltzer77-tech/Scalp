#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv, json, os, sys, time
from collections import Counter

CSV_PATH = os.environ.get("SCALP_SIGNALS_CSV", "/opt/scalp/var/dashboard/signals.csv")

# pagination simple via variables d'env (défaut UI: 100 premiers)
LIMIT  = int(os.environ.get("SCALP_API_LIMIT", 100))
OFFSET = int(os.environ.get("SCALP_API_OFFSET", 0))

VALID_SIDES = {"BUY","SELL","HOLD"}

def parse_details_to_side(details:str) -> str:
    """
    Essaie de déduire BUY/SELL par majorité des composants:
    details="sma_cross_fast=BUY;rsi_reversion=HOLD;ema_trend=BUY"
    -> BUY (2/3)
    """
    if not details:
        return "HOLD"
    votes = Counter()
    for kv in details.split(";"):
        if "=" in kv:
            k,v = kv.split("=",1)
            v = v.strip().upper()
            if v in ("BUY","SELL","HOLD"):
                votes[v] += 1
    # majorité stricte BUY/SELL ? sinon HOLD
    if votes["BUY"] > votes["SELL"] and votes["BUY"] >= 1:
        return "BUY"
    if votes["SELL"] > votes["BUY"] and votes["SELL"] >= 1:
        return "SELL"
    return "HOLD"

def normalize_header(names):
    """
    Mappe symbol->sym, signal->side si besoin.
    Retourne la liste finale d'en-têtes attendues: ts,sym,tf,side,details
    et un dict de mapping {final_col: source_col}.
    """
    lower = [n.strip().lower() for n in names]
    map_src = {}

    # ts
    if "ts" in lower:
        map_src["ts"] = names[lower.index("ts")]
    else:
        raise ValueError("En-tête 'ts' manquant")

    # sym
    if "sym" in lower:
        map_src["sym"] = names[lower.index("sym")]
    elif "symbol" in lower:
        map_src["sym"] = names[lower.index("symbol")]
    else:
        raise ValueError("En-tête 'sym' ou 'symbol' manquant")

    # tf
    if "tf" in lower:
        map_src["tf"] = names[lower.index("tf")]
    else:
        raise ValueError("En-tête 'tf' manquant")

    # side
    if "side" in lower:
        map_src["side"] = names[lower.index("side")]
    elif "signal" in lower:
        map_src["side"] = names[lower.index("signal")]
    else:
        # pas bloquant: on pourra déduire via details
        map_src["side"] = None

    # details
    if "details" in lower:
        map_src["details"] = names[lower.index("details")]
    else:
        map_src["details"] = None

    return ["ts","sym","tf","side","details"], map_src

def read_rows():
    items = []
    if not os.path.isfile(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
        return items

    with open(CSV_PATH, newline="") as f:
        # détecte dynamiquement l'en-tête
        peek = f.readline()
        if not peek:
            return items
        f.seek(0)

        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return items

        final_cols, src = normalize_header(header)

        for raw in reader:
            if not raw or all(not x.strip() for x in raw):
                continue

            row = dict(zip(header, raw))
            # ts
            try:
                ts = int(str(row.get(src["ts"], "")).strip() or int(time.time()))
            except Exception:
                ts = int(time.time())

            # sym, tf
            sym = (row.get(src["sym"], "") or "").strip().upper()
            tf  = (row.get(src["tf"], "")  or "").strip()

            # details (optionnel)
            details = ""
            if src["details"]:
                details = (row.get(src["details"], "") or "").strip()

            # side (colonne si présente), sinon déduction via details
            side = "HOLD"
            if src["side"]:
                side = (row.get(src["side"], "") or "").strip().upper()
                if side not in VALID_SIDES:
                    side = "HOLD"

            if side == "HOLD":  # tente d'améliorer via details
                deduced = parse_details_to_side(details)
                if deduced in ("BUY","SELL"):
                    side = deduced

            # garde uniquement lignes valides
            if not sym or not tf:
                continue

            items.append({
                "ts": ts,
                "sym": sym,
                "tf": tf,
                "side": side,
                "details": details
            })
    return items

def main():
    items = read_rows()

    if not items:
        # fallback minimal et *explicite*
        now = int(time.time())
        items = [
            {"ts": now, "sym":"BTCUSDT", "tf":"1m",  "side":"HOLD", "details":"fallback"},
            {"ts": now, "sym":"BTCUSDT", "tf":"5m",  "side":"HOLD", "details":"fallback"},
            {"ts": now, "sym":"BTCUSDT", "tf":"15m", "side":"HOLD", "details":"fallback"},
        ]

    total = len(items)
    start = max(0, min(OFFSET, total))
    end   = max(start, min(total, start + LIMIT))
    page  = items[start:end]

    out = {
        "total": total,
        "limit": LIMIT,
        "offset": start,
        "items": page
    }
    json.dump(out, sys.stdout, separators=(",",":"))

if __name__ == "__main__":
    main()

