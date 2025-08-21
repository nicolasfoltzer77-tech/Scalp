import json
import logging
import time
import hmac
import hashlib
import base64
import uuid
from typing import Any, Dict, List, Optional

import requests


# Mapping of deprecated v1 product type identifiers to the new v2 names
_PRODUCT_TYPE_ALIASES = {
    "UMCBL": "USDT-FUTURES",
    "DMCBL": "USDC-FUTURES",
    "CMCBL": "COIN-FUTURES",
}

# Granularity aliases from v1 to v2 nomenclature
_GRANULARITY_ALIASES = {
    "MIN1": "1m",
    "MIN3": "3m",
    "MIN5": "5m",
    "MIN15": "15m",
    "MIN30": "30m",
    "HOUR1": "1H",
    "HOUR4": "4H",
    "HOUR12": "12H",
    "DAY1": "1D",
    "WEEK1": "1W",
}


# Default margin coin for each product type. Some authenticated endpoints
# require ``marginCoin`` in addition to ``productType``; supplying a sensible
# default avoids ``400 Bad Request`` responses when the caller does not provide
# it explicitly.
_DEFAULT_MARGIN_COIN = {
    "USDT-FUTURES": "USDT",
    "USDC-FUTURES": "USDC",
}


class BitgetFuturesClient:
    """Lightweight REST client for Bitget LAPI v2 futures endpoints."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        base_url: str,
        *,
        product_type: str = "USDT-FUTURES",
        recv_window: int = 30,
        paper_trade: bool = True,
        requests_module: Any = requests,
        log_event: Optional[Any] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        self.ak = access_key
        self.sk = secret_key
        self.base = base_url.rstrip("/")
        pt = product_type.upper()
        self.product_type = _PRODUCT_TYPE_ALIASES.get(pt, pt)
        self.recv_window = recv_window
        self.paper_trade = paper_trade
        self.requests = requests_module
        self.log_event = log_event or (lambda *a, **k: None)
        self.passphrase = passphrase
        if not self.ak or not self.sk or self.ak == "A_METTRE" or self.sk == "B_METTRE":
            logging.warning(
                "\u26a0\ufe0f Cl\u00e9s API non d\u00e9finies. Le mode r\u00e9el ne fonctionnera pas.",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _urlencode_sorted(params: Dict[str, Any]) -> str:
        if not params:
            return ""
        items = []
        for k in sorted(params.keys()):
            v = "" if params[k] is None else str(params[k])
            items.append(f"{k}={v}")
        return "&".join(items)

    def _sign(self, prehash: str) -> str:
        """Return a base64-encoded HMAC SHA256 signature."""
        digest = hmac.new(self.sk.encode(), prehash.encode(), hashlib.sha256).digest()
        return base64.b64encode(digest).decode()

    def _headers(self, signature: str, timestamp: int) -> Dict[str, str]:
        headers = {
            "ACCESS-KEY": self.ak,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": str(timestamp),
            "ACCESS-RECV-WINDOW": str(self.recv_window),
            "Content-Type": "application/json",
        }
        if self.passphrase:
            headers["ACCESS-PASSPHRASE"] = self.passphrase
        return headers

    def _format_symbol(self, symbol: str) -> str:
        """Return ``symbol`` formatted for Bitget API.

        The v2 endpoints expect the trading pair without any product type
        suffix (``BTCUSDT``). Older configurations may provide symbols like
        ``BTC_USDT`` or ``BTCUSDT_UMCBL``; these are normalised by removing the
        separators and any trailing product type string (legacy or v2).
        """

        if not symbol:
            return symbol

        sym = symbol.replace("_", "").upper()
        # Strip product type suffix if present (e.g. BTCUSDTUMCBL)
        if sym.endswith(self.product_type):
            sym = sym[: -len(self.product_type)]
        else:
            for old in _PRODUCT_TYPE_ALIASES.keys():
                if sym.endswith(old):
                    sym = sym[: -len(old)]
                    break
        return sym

    def _product_type(self, pt: Optional[str] = None) -> str:
        """Normalise ``pt`` to a valid v2 product type identifier."""
        key = (pt or self.product_type or "").upper()
        return _PRODUCT_TYPE_ALIASES.get(key, key)

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------
    def get_contract_detail(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Return futures contract information.

        The previous implementation queried ``/contract-detail`` which does not
        exist on Bitget's v2 API and resulted in a 404 error.  The correct
        endpoint is ``/contracts`` with the symbol supplied as a query
        parameter."""

        url = f"{self.base}/api/v2/mix/market/contracts"
        params: Dict[str, Any] = {"productType": self.product_type}
        if symbol:
            params["symbol"] = self._format_symbol(symbol)
        r = self.requests.get(url, params=params, timeout=15)
        if r.status_code == 404:  # pragma: no cover - depends on network
            logging.error("Contract detail introuvable pour %s", symbol)
            return {"success": False, "code": 404, "data": None}
        r.raise_for_status()
        return r.json()

    def get_kline(
        self,
        symbol: str,
        interval: str = "1m",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Endpoint expects the trading pair in query parameters rather than
        # encoded in the path. Using ``/candles/{symbol}`` results in a 404
        # response from Bitget. See: https://api.bitget.com/api/v2/mix/market/candles
        url = f"{self.base}/api/v2/mix/market/candles"
        interval_norm = _GRANULARITY_ALIASES.get(interval.replace("_", "").upper(), interval)
        params: Dict[str, Any] = {
            "symbol": self._format_symbol(symbol),
            "productType": self.product_type,
            "granularity": interval_norm,
        }
        if start is not None:
            params["startTime"] = int(start)
        if end is not None:
            params["endTime"] = int(end)
        r = self.requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        rows = data.get("data") if isinstance(data, dict) else None
        if isinstance(rows, list) and rows and isinstance(rows[0], list):
            cols = {"ts": [], "open": [], "high": [], "low": [], "close": [], "volume": [], "quoteVolume": []}
            for row in rows:
                if len(row) < 7:
                    continue
                try:
                    ts, op, hi, lo, cl, vol, qv = row[:7]
                    cols["ts"].append(int(ts))
                    cols["open"].append(float(op))
                    cols["high"].append(float(hi))
                    cols["low"].append(float(lo))
                    cols["close"].append(float(cl))
                    cols["volume"].append(float(vol))
                    cols["quoteVolume"].append(float(qv))
                except (TypeError, ValueError):
                    continue
            data["data"] = cols
        elif isinstance(rows, list):
            data["data"] = {"ts": [], "open": [], "high": [], "low": [], "close": [], "volume": [], "quoteVolume": []}
        return data

    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if symbol:
            url = f"{self.base}/api/v2/mix/market/ticker"
            params = {
                "symbol": self._format_symbol(symbol),
                "productType": self.product_type,
            }
        else:
            url = f"{self.base}/api/v2/mix/market/tickers"
            params = {"productType": self.product_type}
        r = self.requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Private endpoints
    # ------------------------------------------------------------------
    def _private_request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        method = method.upper()
        ts = self._ms()

        if method in ("GET", "DELETE"):
            qs = self._urlencode_sorted(params or {})
            req_path = path + (f"?{qs}" if qs else "")
            sig = self._sign(f"{ts}{method}{req_path}")
            headers = self._headers(sig, ts)
            url = f"{self.base}{req_path}"
            r = self.requests.request(method, url, headers=headers, timeout=20)
        elif method == "POST":
            qs = self._urlencode_sorted(params or {})
            req_path = path + (f"?{qs}" if qs else "")
            body_str = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)
            sig = self._sign(f"{ts}{method}{req_path}{body_str}")
            headers = self._headers(sig, ts)
            url = f"{self.base}{req_path}"
            r = self.requests.post(
                url,
                data=body_str.encode("utf-8"),
                headers=headers,
                timeout=20,
            )
        else:
            raise ValueError("M\u00e9thode non support\u00e9e")

        resp_text = getattr(r, "text", "")
        try:
            data = r.json()
        except Exception:
            data = {
                "success": False,
                "error": resp_text,
                "status_code": getattr(r, "status_code", None),
            }

        status = getattr(r, "status_code", 0)
        if status >= 400:
            code = str(data.get("code")) if isinstance(data, dict) else ""
            if code == "22001":
                logging.info("Aucun ordre à annuler (%s %s)", method, path)
            else:
                try:
                    r.raise_for_status()
                except Exception as e:
                    if not resp_text:
                        resp_text = getattr(r, "text", "") or str(e)
                logging.error(
                    "Erreur HTTP/JSON %s %s -> %s %s",
                    method,
                    path,
                    status,
                    resp_text,
                )
                if isinstance(data, dict):
                    data.setdefault("success", False)
                    data.setdefault("status_code", status)
                    data.setdefault("error", resp_text)

        self.log_event(
            "http_private",
            {"method": method, "path": path, "params": params, "body": body, "response": data},
        )
        return data

    # Accounts & positions -------------------------------------------------
    def get_assets(self, margin_coin: Optional[str] = None) -> Dict[str, Any]:
        if self.paper_trade:
            return {
                "success": True,
                "code": 0,
                "data": [
                    {
                        "currency": "USDT",
                        "equity": 100.0,
                    }
                ],
            }

        params = {"productType": self.product_type}
        if margin_coin is None:
            margin_coin = _DEFAULT_MARGIN_COIN.get(self.product_type)
        if margin_coin:
            params["marginCoin"] = margin_coin
        data = self._private_request(
            "GET", "/api/v2/mix/account/accounts", params=params
        )
        try:
            for row in data.get("data", []):
                if "currency" not in row and row.get("marginCoin"):
                    row["currency"] = row["marginCoin"]
        except Exception:  # pragma: no cover - best effort
            pass
        return data

    def get_positions(self, product_type: Optional[str] = None) -> Dict[str, Any]:
        if self.paper_trade:
            return {"success": True, "code": 0, "data": []}
        data = self._private_request(
            "GET",
            "/api/v2/mix/position/all-position",
            params={"productType": self._product_type(product_type)},
        )
        try:
            positions = data.get("data", [])
            filtered = []
            for pos in positions:
                vol = pos.get("vol")
                try:
                    if vol is not None and float(vol) > 0:
                        filtered.append(pos)
                except (TypeError, ValueError):
                    continue
            data["data"] = filtered
        except Exception:  # pragma: no cover - best effort
            pass
        return data

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if self.paper_trade:
            return {"success": True, "code": 0, "data": []}
        params: Dict[str, Any] = {"productType": self.product_type}
        if symbol:
            params["symbol"] = self._format_symbol(symbol)
        return self._private_request("GET", "/api/v2/mix/order/orders-pending", params=params)

    # Account configuration -------------------------------------------------
    def set_position_mode_one_way(self, symbol: str, product_type: Optional[str] = None) -> Dict[str, Any]:
        body = {
            "productType": self._product_type(product_type),
            "symbol": self._format_symbol(symbol),
            "posMode": "one_way_mode",
        }
        return self._private_request("POST", "/api/v2/mix/account/set-position-mode", body=body)

    def set_leverage(
        self,
        symbol: str,
        product_type: Optional[str] = None,
        margin_coin: str = "USDT",
        leverage: int = 1,
    ) -> Dict[str, Any]:
        body = {
            "symbol": self._format_symbol(symbol),
            "productType": self._product_type(product_type),
            "marginCoin": margin_coin,
            "leverage": int(leverage),
        }
        return self._private_request(
            "POST", "/api/v2/mix/account/set-leverage", body=body
        )

    def place_market_order_one_way(
        self,
        symbol: str,
        side: str,
        size: float,
        product_type: Optional[str] = None,
        margin_coin: str = "USDT",
        *,
        time_in_force: str = "normal",
    ) -> Dict[str, Any]:
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        body = {
            "symbol": self._format_symbol(symbol),
            "productType": self._product_type(product_type),
            "marginCoin": margin_coin,
            "marginMode": "crossed",
            "posMode": "one_way_mode",
            "orderType": "market",
            "side": side,
            "size": str(size),
            "timeInForceValue": time_in_force,
            "clientOid": str(uuid.uuid4())[:32],
        }
        return self._private_request(
            "POST", "/api/v2/mix/order/place-order", body=body
        )

    # Orders ---------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: int,
        vol: int,
        order_type: int,
        *,
        price: Optional[float] = None,
        open_type: int = 1,
        leverage: Optional[int] = None,
        position_id: Optional[int] = None,
        external_oid: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        reduce_only: Optional[bool] = None,
        position_mode: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Submit an order."""
        if self.paper_trade:
            logging.info(
                "PAPER_TRADE=True -> ordre simul\u00e9: side=%s vol=%s type=%s price=%s",
                side,
                vol,
                order_type,
                price,
            )
            return {
                "success": True,
                "paperTrade": True,
                "simulated": {
                    "symbol": symbol,
                    "side": side,
                    "vol": vol,
                    "type": order_type,
                    "price": price,
                    "openType": open_type,
                    "leverage": leverage,
                    "stopLossPrice": stop_loss,
                    "takeProfitPrice": take_profit,
                },
            }

        body = {
            "symbol": self._format_symbol(symbol),
            "size": vol,
            "side": side,
            "orderType": order_type,
            "openType": open_type,
        }
        if price is not None:
            body["price"] = float(price)
        if leverage is not None:
            body["leverage"] = int(leverage)
        if position_id is not None:
            body["positionId"] = int(position_id)
        if external_oid:
            body["clientOid"] = str(external_oid)[:32]
        if stop_loss is not None:
            body["stopLossPrice"] = float(stop_loss)
        if take_profit is not None:
            body["takeProfitPrice"] = float(take_profit)
        if reduce_only is not None:
            body["reduceOnly"] = bool(reduce_only)
        if position_mode is not None:
            body["positionMode"] = int(position_mode)

        return self._private_request("POST", "/api/v2/mix/order/place-order", body=body)

    def cancel_order(self, order_ids: List[int]) -> Dict[str, Any]:
        if self.paper_trade:
            logging.info(
                "PAPER_TRADE=True -> annulation simulée: order_ids=%s", order_ids
            )
            return {"success": True, "code": 0}
        return self._private_request(
            "POST", "/api/v2/mix/order/cancel-order", body={"orderIds": order_ids}
        )

    def cancel_all(
        self,
        symbol: Optional[str] = None,
        margin_coin: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.paper_trade:
            logging.info(
                "PAPER_TRADE=True -> annulation simulée de tous les ordres"
            )
            return {"success": True, "code": 0}
        body = {"productType": self.product_type}
        if symbol:
            body["symbol"] = self._format_symbol(symbol)
        if margin_coin is None:
            margin_coin = _DEFAULT_MARGIN_COIN.get(self.product_type)
        if margin_coin:
            body["marginCoin"] = margin_coin
        return self._private_request(
            "POST", "/api/v2/mix/order/cancel-all-orders", body=body
        )

    def close_position(
        self,
        symbol: str,
        size: Optional[int] = None,
        hold_side: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Close an open position for ``symbol``.

        Parameters
        ----------
        symbol:
            Trading symbol to close.
        size:
            Optional number of contracts to close. If omitted the entire
            position is closed.
        hold_side:
            Optional side (``"long"``/``"short"``) to close when ``size`` is
            specified. If not provided the exchange will infer it.
        """

        if self.paper_trade:
            logging.info(
                "PAPER_TRADE=True -> fermeture simulée de la position %s", symbol
            )
            return {"success": True, "code": 0}

        body = {"symbol": self._format_symbol(symbol)}
        if size is not None:
            body["size"] = int(size)
        if hold_side:
            body["holdSide"] = hold_side

        body["productType"] = self.product_type
        return self._private_request(
            "POST", "/api/v2/mix/position/close-position", body=body
        )

    def close_all_positions(self, product_type: Optional[str] = None) -> Dict[str, Any]:
        """Close all open positions."""
        results = []
        try:
            for pos in self.get_positions(product_type).get("data", []):
                sym = pos.get("symbol")
                if sym:
                    results.append(self.close_position(sym))
        except Exception as exc:  # pragma: no cover - best effort
            logging.error("Erreur fermeture de toutes les positions: %s", exc)
        return {"success": True, "data": results}
