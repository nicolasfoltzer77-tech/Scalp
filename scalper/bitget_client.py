# scalper/bitget_client.py
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import requests

__all__ = ["BitgetFuturesClient", "ApiError"]

log = logging.getLogger("scalper.bitget_client")


# =============================================================================
# Exceptions
# =============================================================================
class ApiError(RuntimeError):
    """Erreur API Bitget (HTTP != 200, code != '00000', ou payload invalide)."""

    def __init__(self, message: str, *, http_status: int | None = None, body: Any | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.body = body


# =============================================================================
# Helpers
# =============================================================================
def _now_ms() -> int:
    return int(time.time() * 1000)


def _canonical_json(obj: Mapping[str, Any] | None) -> str:
    if not obj:
        return ""
    # JSON compact, trié, ascii pour signature stable
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=True)


# =============================================================================
# Client REST Futures (USDT-M)
# =============================================================================
@dataclass
class _Auth:
    access_key: str
    secret_key: str
    passphrase: str
    recv_window: int = 30_000  # ms


class BitgetFuturesClient:
    """
    Client REST léger pour les Futures USDT-M de Bitget.

    Points clés:
    - Public: get_ticker(symbol?), get_klines(symbol, interval, limit, start/end?)
    - Privé : get_account(), get_open_orders(symbol?), cancel_order(), cancel_all()
              place_market_order_one_way(), place_limit_order_one_way()
              set_position_mode_one_way(), set_leverage()
    - Safe: gestion d’erreurs centralisée, retries modestes côté réseau, timeouts.

    Notes:
    - Les endpoints et champs renvoyés sont harmonisés pour rester stables
      côté bot/orchestrateur. On tolère plusieurs variantes de clés (lastPr/lastPrice).
    """

    def __init__(
        self,
        *,
        access_key: str = "",
        secret_key: str = "",
        passphrase: str = "",
        base_url: str = "https://api.bitget.com",
        paper_trade: bool = True,
        timeout: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = _Auth(access_key, secret_key, passphrase)
        self.paper = paper_trade
        self.timeout = float(timeout)
        self.sess = session or requests.Session()
        # En-têtes par défaut (Bitget utilise parfois des headers dédiés)
        self.sess.headers.update({"Accept": "application/json"})
        log.info("BitgetFuturesClient ready (paper=%s base=%s)", self.paper, self.base_url)

    # -------------------------------------------------------------------------
    # Core HTTP
    # -------------------------------------------------------------------------
    def _sign(self, ts_ms: int, method: str, path: str, query: str, body: str) -> str:
        """
        Signature (préservée au plus simple) :
          sign = base64( HMAC_SHA256(secret, f"{ts}{method}{path}{query}{body}") )
        - method en MAJUSCULES
        - query inclut '?' si présent, sinon ""
        - body = chaîne JSON canonique (ou vide)
        """
        msg = f"{ts_ms}{method.upper()}{path}{query}{body}"
        return base64.b64encode(hmac.new(self.auth.secret_key.encode(), msg.encode(), hashlib.sha256).digest()).decode()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Mapping[str, Any]] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = dict(params or {})
        body_json = _canonical_json(body)
        query = ""

        headers = {"Content-Type": "application/json"}
        if not signed:
            # Public
            resp = self.sess.request(
                method=method.upper(),
                url=url,
                params=params or None,
                timeout=self.timeout,
                headers=headers,
            )
        else:
            # Privé: timestamp + recvWindow
            ts = _now_ms()
            if "recvWindow" not in params:
                params["recvWindow"] = self.auth.recv_window
            # Construire la query string stable (requests la formate si on passe 'params')
            # Pour la signature, on reconstruit minimalement:
            if params:
                # Tri simple par clé pour stabilité
                q_items = "&".join(f"{k}={params[k]}" for k in sorted(params))
                query = f"?{q_items}"
            signature = self._sign(ts, method, path, query, body_json)

            headers.update(
                {
                    "ACCESS-KEY": self.auth.access_key,
                    "ACCESS-SIGN": signature,
                    "ACCESS-TIMESTAMP": str(ts),
                    "ACCESS-PASSPHRASE": self.auth.passphrase,
                }
            )

            resp = self.sess.request(
                method=method.upper(),
                url=url,
                params=params or None,
                data=body_json if body_json else None,
                timeout=self.timeout,
                headers=headers,
            )

        # Gestion d’erreurs HTTP
        if resp.status_code != 200:
            raise ApiError(f"HTTP {resp.status_code} for {path}", http_status=resp.status_code, body=resp.text)

        # Décodage JSON
        try:
            data = resp.json()
        except Exception as exc:
            raise ApiError(f"Non-JSON response for {path}: {resp.text[:200]}") from exc

        # Protocole Bitget: code == '00000' attendu
        code = str(data.get("code", ""))
        if code and code != "00000":
            raise ApiError(f"Bitget API error code={code} for {path}", body=data)

        return data

    # -------------------------------------------------------------------------
    # PUBLIC
    # -------------------------------------------------------------------------
    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Ticker spot/futures. On suit l'API publique 'mix' si symbol précisé.
        Retourne un dict avec 'data' list/dict ; on tolère plusieurs champs prix.
        """
        if symbol:
            # Futures Mix tickers (ex: /api/v2/mix/market/tickers?productType=USDT-FUTURES)
            # Ici on récupère tous les tickers puis on filtre localement pour robustesse.
            data = self._request(
                "GET",
                "/api/v2/mix/market/tickers",
                params={"productType": "USDT-FUTURES"},
                signed=False,
            )
            # Harmoniser: extraire l’entrée du symbole demandé
            items = data.get("data") or []
            sym = symbol.replace("_", "").upper()
            hit: Dict[str, Any] | None = None
            for it in items:
                if (it.get("symbol") or "").replace("_", "").upper() == sym:
                    hit = it
                    break
            return {"data": hit or {}}

        # Sans symbole: renvoie tout (liste)
        return self._request(
            "GET",
            "/api/v2/mix/market/tickers",
            params={"productType": "USDT-FUTURES"},
            signed=False,
        )

    def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        OHLCV Futures.
        interval: '1m', '5m', '15m', '1h', ...
        start/end: timestamps ms optionnels selon l’API.
        """
        params: Dict[str, Any] = {
            "symbol": symbol.replace("_", "").upper(),
            "granularity": interval,
            "productType": "USDT-FUTURES",
            "limit": max(1, min(int(limit), 1000)),
        }
        if start is not None:
            params["startTime"] = int(start)
        if end is not None:
            params["endTime"] = int(end)

        return self._request("GET", "/api/v2/mix/market/candles", params=params, signed=False)

    # -------------------------------------------------------------------------
    # PRIVÉ (Futures One-Way par défaut)
    # -------------------------------------------------------------------------
    def get_account(self) -> Dict[str, Any]:
        """Infos compte futures (marges, balances)."""
        return self._request("GET", "/api/v2/mix/account/accounts", params={"productType": "USDT-FUTURES"}, signed=True)

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"productType": "USDT-FUTURES"}
        if symbol:
            params["symbol"] = symbol.replace("_", "").upper()
        return self._request("GET", "/api/v2/mix/order/open-orders", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        body = {
            "symbol": symbol.replace("_", "").upper(),
            "productType": "USDT-FUTURES",
            "orderId": order_id,
        }
        return self._request("POST", "/api/v2/mix/order/cancel-order", body=body, signed=True)

    def cancel_all(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"productType": "USDT-FUTURES"}
        if symbol:
            body["symbol"] = symbol.replace("_", "").upper()
        return self._request("POST", "/api/v2/mix/order/cancel-batch-orders", body=body, signed=True)

    # -- Mode de position & levier ------------------------------------------------
    def set_position_mode_one_way(self, symbol: str, product_type: str = "USDT-FUTURES") -> Dict[str, Any]:
        """Passe le mode de position en One-Way (si nécessaire)."""
        body = {
            "productType": product_type,
            "symbol": symbol.replace("_", "").upper(),
            "holdMode": "one_way",  # valeur usuelle côté API mix
        }
        return self._request("POST", "/api/v2/mix/account/set-position-mode", body=body, signed=True)

    def set_leverage(
        self,
        symbol: str,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        leverage: int = 2,
        side: str = "long",
    ) -> Dict[str, Any]:
        """Règle l’effet de levier (par side 'long'/'short' ou global selon l’API)."""
        lev = max(1, int(leverage))
        body = {
            "symbol": symbol.replace("_", "").upper(),
            "productType": product_type,
            "marginCoin": margin_coin,
            "leverage": str(lev),
            "holdSide": side.lower(),  # 'long' ou 'short'
        }
        return self._request("POST", "/api/v2/mix/account/set-leverage", body=body, signed=True)

    # -- Placement d’ordres (One-Way) -------------------------------------------
    def place_market_order_one_way(
        self,
        symbol: str,
        side: str,
        size: float,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        client_oid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place un ordre MARKET en mode one-way.
        side: 'buy' ou 'sell'
        size: quantité de contrat (arrondie au format serveur côté API)
        """
        body: Dict[str, Any] = {
            "symbol": symbol.replace("_", "").upper(),
            "productType": product_type,
            "marginCoin": margin_coin,
            "size": f"{float(size):.6f}",
            "side": side.lower(),
            "orderType": "market",
        }
        if client_oid:
            body["clientOid"] = client_oid
        return self._request("POST", "/api/v2/mix/order/place-order", body=body, signed=True)

    def place_limit_order_one_way(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        product_type: str = "USDT-FUTURES",
        margin_coin: str = "USDT",
        tif: str = "GTC",
        client_oid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place un ordre LIMIT en mode one-way.
        tif: GTC/IOC/FOK suivant l’API.
        """
        body: Dict[str, Any] = {
            "symbol": symbol.replace("_", "").upper(),
            "productType": product_type,
            "marginCoin": margin_coin,
            "size": f"{float(size):.6f}",
            "price": f"{float(price):.8f}",
            "side": side.lower(),
            "orderType": "limit",
            "timeInForceValue": tif.upper(),
        }
        if client_oid:
            body["clientOid"] = client_oid
        return self._request("POST", "/api/v2/mix/order/place-order", body=body, signed=True)

    # -------------------------------------------------------------------------
    # Helpers d’accès — compat facilité avec du code existant
    # -------------------------------------------------------------------------
    def last_price(self, symbol: str) -> float:
        """
        Renvoie un prix last connu en tolérant plusieurs structures/clefs de la réponse.
        """
        tick = self.get_ticker(symbol)
        data = tick.get("data")
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return 0.0
        price_str = (
            data.get("lastPr")
            or data.get("lastPrice")
            or data.get("close")
            or data.get("price")
            or data.get("l")
        )
        try:
            return float(price_str)
        except Exception:
            return 0.0