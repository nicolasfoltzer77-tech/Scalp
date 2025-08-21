import json
import logging
import time
import hmac
import hashlib
import base64
import uuid
from typing import Any, Dict, List, Optional

import requests


class BitgetFuturesClient:
    """Lightweight REST client for Bitget LAPI v2 futures endpoints."""

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        base_url: str,
        *,
        recv_window: int = 30,
        paper_trade: bool = True,
        requests_module: Any = requests,
        log_event: Optional[Any] = None,
        passphrase: Optional[str] = None,
    ) -> None:
        self.ak = access_key
        self.sk = secret_key
        self.base = base_url.rstrip("/")
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

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------
    def get_contract_detail(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v2/mix/market/contract-detail"
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        r = self.requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_kline(
        self,
        symbol: str,
        interval: str = "Min1",
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base}/api/v2/mix/market/candles/{symbol}"
        params: Dict[str, Any] = {"granularity": interval}
        if start is not None:
            params["startTime"] = int(start)
        if end is not None:
            params["endTime"] = int(end)
        r = self.requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v2/mix/market/ticker"
        params: Dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
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
        url = f"{self.base}{path}"
        ts = self._ms()

        if method in ("GET", "DELETE"):
            qs = self._urlencode_sorted(params or {})
            req_path = path + (f"?{qs}" if qs else "")
            sig = self._sign(f"{ts}{method}{req_path}")
            headers = self._headers(sig, ts)
            r = self.requests.request(method, url, params=params, headers=headers, timeout=20)
        elif method == "POST":
            body_str = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)
            sig = self._sign(f"{ts}{method}{path}{body_str}")
            headers = self._headers(sig, ts)
            r = self.requests.post(url, data=body_str.encode("utf-8"), headers=headers, timeout=20)
        else:
            raise ValueError("M\u00e9thode non support\u00e9e")

        try:
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # pragma: no cover - network errors
            logging.error("Erreur HTTP/JSON %s %s -> %s", method, path, str(e))
            data = {
                "success": False,
                "error": str(e),
                "status_code": getattr(r, "status_code", None),
            }
        self.log_event(
            "http_private",
            {"method": method, "path": path, "params": params, "body": body, "response": data},
        )
        return data

    # Accounts & positions -------------------------------------------------
    def get_assets(self) -> Dict[str, Any]:
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
        return self._private_request("GET", "/api/v2/mix/account/accounts")

    def get_positions(self, product_type: str = "umcbl") -> Dict[str, Any]:
        data = self._private_request(
            "GET",
            "/api/v2/mix/position/all-position",
            params={"productType": product_type},
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
        return self._private_request(
            "GET",
            "/api/v2/mix/order/current",
            params={"symbol": symbol} if symbol else None,
        )

    # Account configuration -------------------------------------------------
    def set_position_mode_one_way(self, symbol: str, product_type: str) -> Dict[str, Any]:
        body = {"productType": product_type, "symbol": symbol, "posMode": "one_way_mode"}
        return self._private_request("POST", "/api/v2/mix/account/set-position-mode", body=body)

    def set_leverage(
        self, symbol: str, product_type: str, margin_coin: str, leverage: int
    ) -> Dict[str, Any]:
        body = {
            "symbol": symbol,
            "productType": product_type,
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
        product_type: str,
        margin_coin: str,
        *,
        time_in_force: str = "normal",
    ) -> Dict[str, Any]:
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        body = {
            "symbol": symbol,
            "productType": product_type,
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
            "symbol": symbol,
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

        return self._private_request("POST", "/api/v2/mix/order/place", body=body)

    def cancel_order(self, order_ids: List[int]) -> Dict[str, Any]:
        return self._private_request(
            "POST", "/api/v2/mix/order/cancel-order", body={"orderIds": order_ids}
        )

    def cancel_all(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        body = {"symbol": symbol} if symbol else {}
        return self._private_request("POST", "/api/v2/mix/order/cancel-all-order", body=body)

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an open position for ``symbol``."""
        body = {"symbol": symbol}
        return self._private_request(
            "POST", "/api/v2/mix/position/close-position", body=body
        )

    def close_all_positions(self, product_type: str = "umcbl") -> Dict[str, Any]:
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
