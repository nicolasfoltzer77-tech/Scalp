#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example script to open a one-way short on Bitget futures.

This standalone script signs and sends a market sell order using the
Bitget REST API. Environment variables required (defined in a `.env`
file alongside this script):

- ``BITGET_BASE_URL`` (optional, defaults to ``https://api.bitget.com``)
- ``BITGET_API_KEY``
- ``BITGET_API_SECRET``
- ``BITGET_API_PASSPHRASE``
- ``BITGET_PRODUCT_TYPE`` (e.g. ``USDT-FUTURES``)
- ``BITGET_MARGIN_COIN`` (e.g. ``USDT``)
- ``BITGET_SYMBOL`` (e.g. ``BTCUSDT``)
- ``BITGET_TEST_NOTIONAL_USDT`` (trade notional for test order)

The script retrieves the current contract specification and price,
ensures account settings (one-way mode & leverage) and finally places a
market sell order sized to approximately ``BITGET_TEST_NOTIONAL_USDT``.

The intent is purely demonstrational; use at your own risk.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests

try:  # lazy dependency import for dotenv
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - installation fallback
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv

# load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")


def T(x):  # small helper used throughout configuration
    return x.strip() if isinstance(x, str) else x


BASE = T(os.getenv("BITGET_BASE_URL", "https://api.bitget.com"))
AK = T(os.getenv("BITGET_API_KEY"))
SK = T(os.getenv("BITGET_API_SECRET"))
PH = T(os.getenv("BITGET_API_PASSPHRASE"))
PT = T(os.getenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES"))
MC = T(os.getenv("BITGET_MARGIN_COIN", "USDT"))
SYMB = (T(os.getenv("BITGET_SYMBOL", "BTCUSDT")) or "BTCUSDT").replace("_", "").upper()
NOTIONAL = float(os.getenv("BITGET_TEST_NOTIONAL_USDT", "5.0"))

if not (AK and SK and PH):
    sys.exit("❌ .env incomplet (BITGET_API_KEY/SECRET/PASSPHRASE).")

print(f"Base={BASE}  PT={PT}  SYMB={SYMB}  MC={MC}  Notional≈{NOTIONAL}USDT")


# ---------- signing helpers ----------
def sign_get(ts, path, params):
    qs = "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    pre = f"{ts}GET{path}" + (f"?{qs}" if qs else "")
    return base64.b64encode(hmac.new(SK.encode(), pre.encode(), hashlib.sha256).digest()).decode()


def sign_post(ts, path, body):
    body_str = json.dumps(body or {}, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    pre = f"{ts}POST{path}{body_str}"
    sig = base64.b64encode(hmac.new(SK.encode(), pre.encode(), hashlib.sha256).digest()).decode()
    return sig, body_str


def headers(sig, ts):
    return {
        "ACCESS-KEY": AK,
        "ACCESS-SIGN": sig,
        "ACCESS-TIMESTAMP": str(ts),
        "ACCESS-PASSPHRASE": PH,
        "ACCESS-RECV-WINDOW": "60000",
        "Content-Type": "application/json",
    }


def pick_price(d: dict):
    for k in ("last", "price", "close", "bestAsk", "bestBid", "markPrice", "settlementPrice"):
        try:
            v = float(d.get(k))
            if v > 0:
                return v
        except Exception:
            pass
    return None


# ---------- public endpoints ----------
def get_contract_spec():
    r = requests.get(
        f"{BASE}/api/v2/mix/market/contracts",
        params={"productType": PT, "symbol": SYMB},
        timeout=12,
    )
    r.raise_for_status()
    arr = r.json().get("data") or []
    if not arr:
        raise RuntimeError("Contrat introuvable")
    return arr[0]


def get_price():
    # 1) ticker (obj/list) avec productType
    try:
        r = requests.get(
            f"{BASE}/api/v2/mix/market/ticker",
            params={"symbol": SYMB, "productType": PT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("data")
        if isinstance(data, dict):
            p = pick_price(data)
            if p:
                return p
        if isinstance(data, list) and data:
            p = pick_price(data[0])
            if p:
                return p
    except requests.HTTPError as e:
        print("⚠️ ticker HTTP:", e.response.status_code, e.response.text[:140])
    except Exception as e:
        print("⚠️ ticker err:", e)

    # 2) tickers (liste entière)
    try:
        r = requests.get(
            f"{BASE}/api/v2/mix/market/tickers",
            params={"productType": PT},
            timeout=10,
        )
        r.raise_for_status()
        arr = r.json().get("data") or []
        row = next((x for x in arr if (x.get("symbol") or "").upper() == SYMB), None)
        p = pick_price(row or {})
        if p:
            return p
    except requests.HTTPError as e:
        print("⚠️ tickers HTTP:", e.response.status_code, e.response.text[:140])
    except Exception as e:
        print("⚠️ tickers err:", e)

    # 3) candles Min1 (close)
    try:
        # ``symbol`` must be provided as a query parameter; placing it in the
        # path triggers a 404 response from Bitget.
        r = requests.get(
            f"{BASE}/api/v2/mix/market/candles",
            params={"symbol": SYMB, "granularity": "Min1"},
            timeout=10,
        )
        r.raise_for_status()
        arr = r.json().get("data") or []
        if arr:
            return float(arr[0][4])
    except requests.HTTPError as e:
        print("⚠️ candles HTTP:", e.response.status_code, e.response.text[:140])
    except Exception as e:
        print("⚠️ candles err:", e)

    raise RuntimeError("prix indisponible")


# ---------- private endpoints ----------
def check_accounts():
    path = "/api/v2/mix/account/accounts"
    ts = int(time.time() * 1000)
    params = {"productType": PT}
    sig = sign_get(ts, path, params)
    r = requests.get(BASE + path, params=params, headers=headers(sig, ts), timeout=12)
    print("accounts", r.status_code, r.text[:160])
    r.raise_for_status()
    j = r.json()
    if str(j.get("code")) not in ("00000", "0"):
        raise RuntimeError(j)


def set_position_mode_one_way():
    path = "/api/v2/mix/account/set-position-mode"
    ts = int(time.time() * 1000)
    body = {"productType": PT, "symbol": SYMB, "posMode": "one_way_mode"}
    sig, b = sign_post(ts, path, body)
    r = requests.post(BASE + path, headers=headers(sig, ts), data=b.encode(), timeout=12)
    print("set-position-mode(one-way)", r.status_code, r.text[:160])
    r.raise_for_status()


def set_leverage(lv: int = 2):
    path = "/api/v2/mix/account/set-leverage"
    ts = int(time.time() * 1000)
    body = {"symbol": SYMB, "productType": PT, "marginCoin": MC, "leverage": int(lv)}
    sig, b = sign_post(ts, path, body)
    r = requests.post(BASE + path, headers=headers(sig, ts), data=b.encode(), timeout=12)
    print("set-leverage", r.status_code, r.text[:160])
    r.raise_for_status()


def place_one_way_sell(size_coin: float):
    """Ouvre un SHORT en one_way_mode (market SELL)."""
    path = "/api/v2/mix/order/place-order"
    ts = int(time.time() * 1000)
    body = {
        "symbol": SYMB,
        "productType": PT,
        "marginCoin": MC,
        "marginMode": "crossed",
        "posMode": "one_way_mode",
        "orderType": "market",
        "side": "sell",  # <-- SHORT
        "size": str(size_coin),
        "timeInForceValue": "normal",
        "clientOid": str(uuid.uuid4())[:32],
    }
    sig, b = sign_post(ts, path, body)
    r = requests.post(BASE + path, headers=headers(sig, ts), data=b.encode(), timeout=15)
    print("place-order(one-way SELL)", r.status_code, r.text[:220])
    r.raise_for_status()
    j = r.json()
    if str(j.get("code")) not in ("00000", "0"):
        raise RuntimeError(j)
    return j


# ---------- main ----------
def main():
    spec = get_contract_spec()
    min_usdt = float(spec.get("minTradeUSDT") or 5)
    min_num = float(spec.get("minTradeNum") or 0)
    size_place = int(spec.get("sizePlace") or 6)
    print(f"Spec OK | minUSDT={min_usdt} minNum={min_num} sizePlace={size_place}")

    px = get_price()
    print(f"Prix OK ≈ {px}")

    check_accounts()
    set_position_mode_one_way()
    set_leverage(2)

    target = max(NOTIONAL, min_usdt)
    size = max(target / px, min_num)
    size = float(f"{size:.{size_place}f}")
    print(f"Taille={size} (target≈{target}USDT)")

    j = place_one_way_sell(size)
    print("✅ SHORT OK")
    print(json.dumps(j, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
