import json
import logging
import time
import hmac
import hashlib
from typing import Any, Dict, List, Optional

import requests


class MexcFuturesClient:
    """Lightweight REST client for MEXC futures endpoints."""

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
    ) -> None:
        self.ak = access_key
        self.sk = secret_key
        self.base = base_url.rstrip("/")
        self.recv_window = recv_window
        self.paper_trade = paper_trade
        self.requests = requests_module
        self.log_event = log_event or (lambda *a, **k: None)
        if not self.ak or not self.sk or self.ak == "A_METTRE" or self.sk == "B_METTRE":
            logging.warning(
                "\u26a0\ufe0f Cl\u00e9s API non d\u00e9finies. Le mode r\u00e9el ne fonctionnera pas."
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

    def _sign(self, request_param_string: str, req_ms: int) -> str:
        msg = f"{self.ak}{req_ms}{request_param_string}"
        return hmac.new(self.sk.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def _headers(self, signature: str, req_ms: int) -> Dict[str, str]:
        return {
            "ApiKey": self.ak,
            "Request-Time": str(req_ms),
            "Signature": signature,
            "Content-Type": "application/json",
            "Recv-Window": str(self.recv_window),
        }

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------
    def get_contract_detail(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v1/contract/detail"
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
        url = f"{self.base}/api/v1/contract/kline/{symbol}"
        params: Dict[str, Any] = {"interval": interval}
        if start is not None:
            params["start"] = int(start)
        if end is not None:
            params["end"] = int(end)
        r = self.requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v1/contract/ticker"
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
        req_ms = self._ms()

        if method in ("GET", "DELETE"):
            qs = self._urlencode_sorted(params or {})
            sig = self._sign(qs, req_ms)
            headers = self._headers(sig, req_ms)
            r = self.requests.request(method, url, params=params, headers=headers, timeout=20)
        elif method == "POST":
            body_str = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)
            sig = self._sign(body_str, req_ms)
            headers = self._headers(sig, req_ms)
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
        return self._private_request("GET", "/api/v1/private/account/assets")

    def get_positions(self) -> Dict[str, Any]:
        return self._private_request(
            "GET",
            "/api/v1/private/position/list/history_positions",
            params={"page_num": 1, "page_size": 50},
        )

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        return self._private_request(
            "GET",
            "/api/v1/private/order/list/open_orders",
            params={"symbol": symbol} if symbol else None,
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
            "vol": vol,
            "side": side,
            "type": order_type,
            "openType": open_type,
        }
        if price is not None:
            body["price"] = float(price)
        if leverage is not None:
            body["leverage"] = int(leverage)
        if position_id is not None:
            body["positionId"] = int(position_id)
        if external_oid:
            body["externalOid"] = str(external_oid)[:32]
        if stop_loss is not None:
            body["stopLossPrice"] = float(stop_loss)
        if take_profit is not None:
            body["takeProfitPrice"] = float(take_profit)
        if reduce_only is not None:
            body["reduceOnly"] = bool(reduce_only)
        if position_mode is not None:
            body["positionMode"] = int(position_mode)

        return self._private_request("POST", "/api/v1/private/order/submit", body=body)

    def cancel_order(self, order_ids: List[int]) -> Dict[str, Any]:
        return self._private_request("POST", "/api/v1/private/order/cancel", body=order_ids)

    def cancel_all(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        body = {"symbol": symbol} if symbol else {}
        return self._private_request("POST", "/api/v1/private/order/cancel_all", body=body)

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an open position for ``symbol``.

        The MEXC API exposes dedicated endpoints to force close positions.
        On startup the trading bot uses this method to ensure no leftover
        positions remain from a previous run.  When running in paper mode the
        request is still logged but otherwise has no effect.
        """

        body = {"symbol": symbol}
        return self._private_request(
            "POST", "/api/v1/private/position/close_position", body=body
        )

    def close_all_positions(self) -> Dict[str, Any]:
        """Close all open positions.

        Used during bot initialisation to guarantee a clean trading state.
        """

        return self._private_request(
            "POST", "/api/v1/private/position/close_all_positions", body={}
        )
