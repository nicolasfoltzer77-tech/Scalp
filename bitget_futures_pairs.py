#!/usr/bin/env python3
"""Fetch the list of Bitget futures contracts.

This helper script queries the public Bitget REST API to retrieve futures
trading pairs for the specified product types and saves them to CSV and JSON
files. It mirrors the standalone example provided by the user but integrates
with the repository's configuration system.

Usage examples::

    python bitget_futures_pairs.py
    python bitget_futures_pairs.py --types USDT-FUTURES COIN-FUTURES
    python bitget_futures_pairs.py --out pairs.csv --json-out pairs.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from typing import Any, Dict, List

from scalp.bot_config import CONFIG

try:  # pragma: no cover - import guard
    import requests
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    sys.stderr.write(
        "This script requires the 'requests' package. Install it with:\n  pip install requests\n"
    )
    raise

BASE_URL = CONFIG.get("BASE_URL", "https://api.bitget.com")
CONTRACTS_ENDPOINT = "/api/v2/mix/market/contracts"
DEFAULT_PRODUCT_TYPES = ["USDT-FUTURES", "USDC-FUTURES", "COIN-FUTURES"]


def fetch_contracts(product_type: str, timeout: float = 10.0) -> List[Dict[str, Any]]:
    """Return contract metadata for ``product_type``."""
    url = f"{BASE_URL}{CONTRACTS_ENDPOINT}"
    params = {"productType": product_type}
    resp = requests.get(url, params=params, timeout=timeout)
    try:
        data = resp.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - network failure
        raise RuntimeError(
            f"Non-JSON response from Bitget API for {product_type}: {resp.text[:200]}"
        ) from exc
    if resp.status_code != 200 or data.get("code") != "00000":
        raise RuntimeError(f"Bitget API error for {product_type}: HTTP {resp.status_code} body={data}")
    return data.get("data", [])


def normalize_rows(product_type: str, contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Select and rename key fields for CSV/JSON output."""
    rows: List[Dict[str, Any]] = []
    for c in contracts:
        row = {
            "productType": product_type,
            "symbol": c.get("symbol"),
            "baseCoin": c.get("baseCoin"),
            "quoteCoin": c.get("quoteCoin"),
            "symbolType": c.get("symbolType"),
            "symbolStatus": c.get("symbolStatus"),
            "maxLever": c.get("maxLever"),
            "minLever": c.get("minLever"),
            "minTradeNum": c.get("minTradeNum"),
            "sizeMultiplier": c.get("sizeMultiplier"),
            "pricePlace": c.get("pricePlace"),
            "volumePlace": c.get("volumePlace"),
            "launchTime": c.get("launchTime"),
            "deliveryTime": c.get("deliveryTime"),
        }
        rows.append(row)
    return rows


def write_csv(rows: List[Dict[str, Any]], path: str) -> None:
    """Write ``rows`` to ``path`` in CSV format."""
    headers = [
        "productType",
        "symbol",
        "baseCoin",
        "quoteCoin",
        "symbolType",
        "symbolStatus",
        "maxLever",
        "minLever",
        "minTradeNum",
        "sizeMultiplier",
        "pricePlace",
        "volumePlace",
        "launchTime",
        "deliveryTime",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Bitget futures pairs (contracts) and save to CSV/JSON."
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=DEFAULT_PRODUCT_TYPES,
        help="Product types to fetch. Choices: USDT-FUTURES, USDC-FUTURES, COIN-FUTURES",
    )
    parser.add_argument("--out", default="bitget_futures_pairs.csv", help="CSV output file path")
    parser.add_argument(
        "--json-out", default="bitget_futures_pairs.json", help="JSON output file path"
    )
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between requests")
    args = parser.parse_args(argv)

    all_rows: List[Dict[str, Any]] = []
    merged_json: Dict[str, List[Dict[str, Any]]] = {}

    for i, pt in enumerate(args.types):
        try:
            contracts = fetch_contracts(pt)
        except Exception as exc:  # pragma: no cover - network/runtime error
            sys.stderr.write(f"[!] Failed to fetch {pt}: {exc}\n")
            continue
        rows = normalize_rows(pt, contracts)
        all_rows.extend(rows)
        merged_json[pt] = contracts
        if i < len(args.types) - 1 and args.sleep > 0:
            time.sleep(args.sleep)

    all_rows.sort(key=lambda r: (r.get("productType") or "", r.get("symbol") or ""))

    write_csv(all_rows, args.out)
    with open(args.json_out, "w", encoding="utf-8") as fh:
        json.dump(merged_json, fh, ensure_ascii=False, indent=2)

    counts = {pt: len(merged_json.get(pt, [])) for pt in args.types}
    total = sum(counts.values())
    print(
        f"Saved {total} futures pairs across {len(args.types)} product types to '{args.out}' and '{args.json_out}'."
    )
    for pt, n in counts.items():
        print(f"  - {pt}: {n} pairs")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI execution
    raise SystemExit(main())
