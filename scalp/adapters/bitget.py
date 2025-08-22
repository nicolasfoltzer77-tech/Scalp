# scalp/adapters/bitget.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import inspect, os
import requests

# Client bas-niveau fourni par le repo
from scalp.bitget_client import BitgetFuturesClient as _Base


def _to_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _select_base_url() -> str:
    env = os.environ.get("BITGET_BASE_URL")
    if env:
        return env
    paper = os.environ.get("PAPER_TRADE", "true").lower() in ("1", "true", "yes", "on")
    return "https://api-testnet.bitget.com" if paper else "https://api.bitget.com"


class BitgetFuturesClient(_Base):
    """
    Adaptateur Bitget:
      - __init__ dynamique (passe seulement les kwargs que le client accepte)
      - Normalisations robustes: assets, ticker(s), positions, fills
    """

    # --------------------- INIT dynamique ---------------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Accepte indifféremment:
          api_key/apiKey/access_key/accessKey/key
          api_secret/apiSecret/secret/secret_key/secretKey
          passphrase/password/api_passphrase/apiPassphrase
          base_url/baseUrl/host/endpoint (ou auto)
        On n'envoie au client de base que les noms présents dans sa signature.
        """
        user_kwargs = dict(kwargs)

        # Collecte des valeurs possibles (tous alias)
        incoming_key = (
            user_kwargs.pop("api_key", None)
            or user_kwargs.pop("apiKey", None)
            or user_kwargs.pop("access_key", None)
            or user_kwargs.pop("accessKey", None)
            or user_kwargs.pop("key", None)
            or user_kwargs.pop("API_KEY", None)
        )
        incoming_secret = (
            user_kwargs.pop("api_secret", None)
            or user_kwargs.pop("apiSecret", None)
            or user_kwargs.pop("secret_key", None)
            or user_kwargs.pop("secretKey", None)
            or user_kwargs.pop("secret", None)
            or user_kwargs.pop("API_SECRET", None)
        )
        incoming_pass = (
            user_kwargs.pop("passphrase", None)
            or user_kwargs.pop("password", None)
            or user_kwargs.pop("api_passphrase", None)
            or user_kwargs.pop("apiPassphrase", None)
        )
        incoming_base = (
            user_kwargs.pop("base_url", None)
            or user_kwargs.pop("baseUrl", None)
            or user_kwargs.pop("host", None)
            or user_kwargs.pop("endpoint", None)
            or _select_base_url()
        )

        # Signature réelle du client bas-niveau
        sig = inspect.signature(_Base.__init__)
        param_names = set(sig.parameters.keys())  # ex: {'self','access_key','secret_key','passphrase','base_url',...}

        def pick_name(cands: List[str]) -> Optional[str]:
            for c in cands:
                if c in param_names:
                    return c
            return None

        # Noms réellement supportés
        key_name = pick_name(["api_key", "apiKey", "access_key", "accessKey", "key"])
        sec_name = pick_name(["api_secret", "apiSecret", "secret_key", "secretKey", "secret"])
        pas_name = pick_name(["passphrase", "password", "api_passphrase", "apiPassphrase"])
        base_name = pick_name(["base_url", "baseUrl", "host", "endpoint"])
        req_mod_name = "requests_module" if "requests_module" in param_names else None

        # Construire kwargs à transmettre (une seule fois par nom)
        base_kwargs: Dict[str, Any] = {}
        if key_name and incoming_key is not None:
            base_kwargs[key_name] = incoming_key
        if sec_name and incoming_secret is not None:
            base_kwargs[sec_name] = incoming_secret
        if pas_name and incoming_pass is not None:
            base_kwargs[pas_name] = incoming_pass
        if base_name:
            base_kwargs[base_name] = incoming_base
        if req_mod_name:
            base_kwargs[req_mod_name] = requests

        # Ne transmettre aucun doublon : si user_kwargs contient un nom supporté
        # qui n'a pas été défini ci-dessus, on le relaie.
        for k, v in list(user_kwargs.items()):
            if k in param_names and k not in base_kwargs:
                base_kwargs[k] = v

        # Appel propre, 100% mots-clés (évite “missing positional arg” et “multiple values”)
        super().__init__(**base_kwargs)

    # --------------------- COMPTES / ASSETS ---------------------
    def get_assets(self) -> Dict[str, Any]:
        raw = super().get_assets()
        data = raw.get("data") or raw.get("result") or raw.get("assets") or []
        norm: List[Dict[str, Any]] = []
        for a in data:
            currency = a.get("currency") or a.get("marginCoin") or a.get("coin") or "USDT"
            equity = _to_float(a.get("equity", a.get("usdtEquity", a.get("totalEquity", 0))))
            available = _to_float(a.get("available", a.get("availableBalance", a.get("availableUSDT", 0))))
            norm.append({"currency": currency, "equity": equity, "available": available, **a})
        return {"success": True, "data": norm}

    # ------------------------ TICKER(S) -------------------------
    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Normalise vers liste d'objets: {symbol,lastPrice,bidPrice,askPrice,volume}
        Tolère top-level dict/list et items dict/list.
        """
        try:
            raw: Any = super().get_ticker(symbol) if symbol else super().get_tickers()
        except Exception as e:
            return {"success": False, "error": repr(e), "data": []}

        items: List[Any] = []
        if isinstance(raw, dict):
            d = raw.get("data")
            if symbol and isinstance(d, dict):
                items = [d]
            else:
                items = d or raw.get("result") or raw.get("tickers") or []
        elif isinstance(raw, (list, tuple)):
            items = list(raw)

        norm: List[Dict[str, Any]] = []
        for t in items:
            if isinstance(t, dict):
                s = (t.get("symbol") or t.get("instId") or t.get("instrumentId") or "").replace("_", "")
                last_ = t.get("lastPrice", t.get("last", t.get("close", t.get("markPrice", 0))))
                bid_ = t.get("bidPrice", t.get("bestBidPrice", t.get("bestBid", t.get("buyOne", last_))))
                ask_ = t.get("askPrice", t.get("bestAskPrice", t.get("bestAsk", t.get("sellOne", last_))))
                vol_usdt = t.get("usdtVolume", t.get("quoteVolume", t.get("turnover24h", None)))
                vol_base = t.get("baseVolume", t.get("volume", t.get("size24h", 0)))
                volume = _to_float(vol_usdt if vol_usdt is not None else vol_base)
                norm.append({
                    "symbol": s,
                    "lastPrice": _to_float(last_),
                    "bidPrice": _to_float(bid_),
                    "askPrice": _to_float(ask_),
                    "volume": volume
                })
            else:
                seq = list(t)
                if len(seq) >= 5:
                    first_ts = isinstance(seq[0], (int, float)) and seq[0] > 10**10
                    if first_ts:
                        close = _to_float(seq[4]); vol = _to_float(seq[5] if len(seq) > 5 else 0.0)
                    else:
                        close = _to_float(seq[3]); vol = _to_float(seq[4] if len(seq) > 4 else 0.0)
                else:
                    close = _to_float(seq[-1] if seq else 0.0); vol = 0.0
                s = (symbol or "").replace("_", "")
                norm.append({"symbol": s, "lastPrice": close, "bidPrice": close, "askPrice": close, "volume": vol})

        return {"success": True, "data": norm}

    # --------------- POSITIONS / ORDRES / FILLS -----------------
    def get_open_positions(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        raw: Dict[str, Any] = super().get_positions() if hasattr(super(), "get_positions") else {}
        items = raw.get("data") or raw.get("result") or raw.get("positions") or []
        out: List[Dict[str, Any]] = []
        for p in items:
            s = (p.get("symbol") or p.get("instId") or "").replace("_", "")
            if symbol and s != symbol:
                continue
            side = (p.get("holdSide") or p.get("posSide") or p.get("side") or "").lower()
            qty = _to_float(p.get("size", p.get("holdAmount", p.get("total", 0))))
            avg = _to_float(p.get("avgOpenPrice", p.get("avgPrice", p.get("entryPrice", 0))))
            out.append({"symbol": s, "side": side, "qty": qty, "avgEntryPrice": avg})
        return {"success": True, "data": out}

    def get_fills(self, symbol: str, order_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        raw: Dict[str, Any] = super().get_fills(symbol=symbol) if hasattr(super(), "get_fills") else {}
        items = raw.get("data") or raw.get("result") or []
        out: List[Dict[str, Any]] = []
        for f in items[:limit]:
            s = (f.get("symbol") or f.get("instId") or "").replace("_", "")
            if s != symbol:
                continue
            if order_id and str(f.get("orderId") or f.get("ordId") or "") != str(order_id):
                continue
            out.append({
                "orderId": str(f.get("orderId") or f.get("ordId") or ""),
                "tradeId": str(f.get("tradeId") or f.get("fillId") or f.get("execId") or ""),
                "price": _to_float(f.get("price", f.get("fillPx", 0))),
                "qty": _to_float(f.get("size", f.get("fillSz", 0))),
                "fee": _to_float(f.get("fee", f.get("fillFee", 0))),
                "ts": int(f.get("ts", f.get("time", 0))),
            })
        return {"success": True, "data": out}

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        raw = super().cancel_order(symbol=symbol, orderId=order_id) if hasattr(super(), "cancel_order") else {}
        ok = bool(raw.get("success", True)) if isinstance(raw, dict) else True
        return {"success": ok, "data": {"orderId": order_id}}