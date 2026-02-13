#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import sqlite3
import time

DB = "/opt/scalp/project/data/contracts.db"

# ============================================================
# UTIL : parse float safe
# ============================================================

def parse_float(x, default=0.0):
    """
    Convertit proprement n'importe quelle valeur Bitget en float.
    - '', None  -> default
    - '123.45'  -> 123.45
    """
    if x is None:
        return default
    if isinstance(x, (int, float)):
        return float(x)
    x = str(x).strip()
    if x == "":
        return default
    try:
        return float(x)
    except:
        return default

# ============================================================
# TABLE SCHEMA
# ============================================================

schema = """
CREATE TABLE IF NOT EXISTS contracts (
    symbol TEXT PRIMARY KEY,
    baseCoin TEXT,
    quoteCoin TEXT,
    minTradeNum REAL,
    minTradeUSDT REAL,
    pricePlace INTEGER,
    volumePlace INTEGER,
    sizeMultiplier REAL,
    minLever INTEGER,
    maxLever INTEGER,
    makerFee REAL,
    takerFee REAL,
    maxOrderQty REAL,
    maxMarketOrderQty REAL,
    symbolStatus TEXT,
    last_update INTEGER
);
"""

# ============================================================
# FETCH FROM BITGET
# ============================================================

URL = "https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures"

def fetch():
    r = requests.get(URL, timeout=5)
    r.raise_for_status()
    data = r.json()
    return data["data"]

# ============================================================
# SAVE TO DB
# ============================================================

def save(rows):
    conn = sqlite3.connect(DB)
    conn.execute(schema)

    query = """
    INSERT OR REPLACE INTO contracts (
        symbol, baseCoin, quoteCoin,
        minTradeNum, minTradeUSDT,
        pricePlace, volumePlace, sizeMultiplier,
        minLever, maxLever,
        makerFee, takerFee,
        maxOrderQty, maxMarketOrderQty,
        symbolStatus, last_update
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    now = int(time.time() * 1000)

    for d in rows:
        conn.execute(query, (
            d.get("symbol"),
            d.get("baseCoin"),
            d.get("quoteCoin"),

            parse_float(d.get("minTradeNum")),
            parse_float(d.get("minTradeUSDT")),

            int(parse_float(d.get("pricePlace"))),
            int(parse_float(d.get("volumePlace"))),
            parse_float(d.get("sizeMultiplier")),

            int(parse_float(d.get("minLever"), 1)),
            int(parse_float(d.get("maxLever"), 1)),

            parse_float(d.get("makerFeeRate")),
            parse_float(d.get("takerFeeRate")),

            parse_float(d.get("maxOrderQty")),
            parse_float(d.get("maxMarketOrderQty")),

            d.get("symbolStatus", "unknown"),
            now
        ))

    conn.commit()
    conn.close()

# ============================================================
# MAIN
# ============================================================

def main():
    rows = fetch()
    save(rows)
    print(f"Saved {len(rows)} contracts into contracts.db")

if __name__ == "__main__":
    main()

