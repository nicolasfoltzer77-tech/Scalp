import os
import time
import hmac
import hashlib
import logging
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.bitget.com"
RECV_WINDOW = 5000


def load_keys() -> Dict[str, str]:
    parent = Path(__file__).resolve().parent.parent
    load_dotenv(parent / ".env")
    api_key = os.getenv("BITGET_API_KEY")
    api_secret = os.getenv("BITGET_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("API keys not found in environment")
    return {"key": api_key, "secret": api_secret}


class BitgetClient:
    def __init__(self) -> None:
        creds = load_keys()
        self.api_key = creds["key"]
        self.api_secret = creds["secret"]
        self.session = requests.Session()
        self.session.headers.update({"X-BITGET-APIKEY": self.api_key})
        self.time_offset = self._compute_time_offset()

    def _compute_time_offset(self) -> int:
        server = self.server_time()
        return int(server["serverTime"]) - int(time.time() * 1000)

    def _timestamp(self) -> int:
        return int(time.time() * 1000) + self.time_offset

    def _request(
        self, method: str, path: str, params: Dict[str, Any] | None = None, *, signed: bool = False
    ) -> Any:
        params = params or {}
        if signed:
            params["timestamp"] = self._timestamp()
            params["recvWindow"] = RECV_WINDOW
            query = urlencode(params)
            signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
            query += f"&signature={signature}"
            headers = {"X-BITGET-APIKEY": self.api_key}
            if method.upper() == "GET":
                url = f"{BASE_URL}{path}?{query}"
                resp = self.session.get(url, headers=headers)
            else:
                url = f"{BASE_URL}{path}"
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                resp = self.session.post(url, data=query, headers=headers)
        else:
            url = f"{BASE_URL}{path}"
            resp = self.session.request(method, url, params=params)

        resp.raise_for_status()
        if resp.text:
            return resp.json()
        return {}

    # Helpers
    def server_time(self) -> Any:
        return self._request("GET", "/api/v3/time")

    def ticker_price(self, symbol: str) -> Any:
        return self._request("GET", "/api/v3/ticker/price", {"symbol": symbol})

    def klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> Any:
        return self._request(
            "GET", "/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit}
        )

    def test_order(self, **params: Any) -> Any:
        return self._request("POST", "/api/v3/order/test", params, signed=True)

    def place_order(self, **params: Any) -> Any:
        return self._request("POST", "/api/v3/order", params, signed=True)

    def account_info(self) -> Any:
        return self._request("GET", "/api/v3/account", signed=True)

    def book_ticker(self, symbol: str) -> Any:
        return self._request("GET", "/api/v3/ticker/bookTicker", {"symbol": symbol})


def sma(values: List[float], period: int) -> float:
    if len(values) < period:
        raise ValueError("Not enough data for SMA")
    return sum(values[-period:]) / period


def analyze(client: BitgetClient, symbol: str, quote_usdt: float, dry_run: bool) -> None:
    kl = client.klines(symbol, limit=50)
    closes = [float(k[4]) for k in kl]
    sma9_prev = sma(closes[:-1], 9)
    sma21_prev = sma(closes[:-1], 21)
    sma9_curr = sma(closes, 9)
    sma21_curr = sma(closes, 21)

    cross_up = sma9_prev <= sma21_prev and sma9_curr > sma21_curr
    cross_down = sma9_prev >= sma21_prev and sma9_curr < sma21_curr

    log = logging.getLogger("bitget_bot")

    if cross_up:
        book = client.book_ticker(symbol)
        ask = float(book["askPrice"])
        qty = quote_usdt / ask
        params = {
            "symbol": symbol,
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "IOC",
            "quantity": f"{qty:.6f}",
            "price": book["askPrice"],
        }
        log.info("BUY signal %s", params)
        resp = client.test_order(**params) if dry_run else client.place_order(**params)
        log.info("response %s", resp)
    elif cross_down:
        account = client.account_info()
        base = symbol.rstrip("USDT")
        bal = next((b for b in account["balances"] if b["asset"] == base), {"free": "0"})
        qty = float(bal["free"])
        if qty > 0:
            book = client.book_ticker(symbol)
            params = {
                "symbol": symbol,
                "side": "SELL",
                "type": "LIMIT",
                "timeInForce": "IOC",
                "quantity": f"{qty:.6f}",
                "price": book["bidPrice"],
            }
            log.info("SELL signal %s", params)
            resp = client.test_order(**params) if dry_run else client.place_order(**params)
            log.info("response %s", resp)
        else:
            log.info("No balance to sell")


def interval_seconds(interval: str) -> int:
    unit = interval[-1]
    qty = int(interval[:-1])
    if unit == "m":
        return qty * 60
    if unit == "h":
        return qty * 3600
    if unit == "d":
        return qty * 86400
    return 60


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = ArgumentParser(description="Bitget SMA crossover bot")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--quote-usdt", type=float, default=10.0)
    parser.add_argument("--interval", default="1m")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--live", dest="dry_run", action="store_false")
    parser.set_defaults(dry_run=True)
    args = parser.parse_args()

    client = BitgetClient()
    delay = interval_seconds(args.interval)

    while True:
        try:
            analyze(client, args.symbol, args.quote_usdt, args.dry_run)
        except Exception as exc:
            logging.getLogger("bitget_bot").error("Error: %s", exc, exc_info=True)
        if not args.loop:
            break
        time.sleep(delay)


if __name__ == "__main__":
    main()
