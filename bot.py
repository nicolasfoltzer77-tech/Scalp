#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MEXC USDT-M Futures Bot – prêt à coller sur Paperspace

Fonctions clés
- Récupère les données marché (klines) via REST MEXC "contract" (futures)
- Stratégie simple (croisement d'EMA) + gestion du risque + SL/TP
- Place/annule des ordres si PAPER_TRADE=False (endpoints privés)
- Journalise toutes les requêtes (fichiers .log et .jsonl)
- AUCUNE commande terminal requise : auto-install de 'requests' si besoin

Sécurité
- Par défaut PAPER_TRADE=True (aucun ordre envoyé)
- Dimensionne la taille via equity, levier et contractSize
- Respecte la signature HMAC-SHA256 (headers: ApiKey, Request-Time, Signature)

© 2025 — Usage à vos risques. Ceci n’est pas un conseil financier.
"""

import os, sys, json, time, hmac, hashlib, logging, math
from urllib.parse import quote
from typing import Dict, Any, Optional, List

from scalp.logging_utils import get_jsonl_logger

# ---------------------------------------------------------------------------
# Dépendances (auto-install si absentes, sans terminal)
# ---------------------------------------------------------------------------
try:
    import requests
except ModuleNotFoundError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# ---------------------------------------------------------------------------
# Configuration (via variables d'env conseillées sur Paperspace)
# ---------------------------------------------------------------------------
CONFIG = {
    "MEXC_ACCESS_KEY": os.getenv("MEXC_ACCESS_KEY", "A_METTRE"),
    "MEXC_SECRET_KEY": os.getenv("MEXC_SECRET_KEY", "B_METTRE"),
    "PAPER_TRADE": os.getenv("PAPER_TRADE", "true").lower() in ("1","true","yes","y"),
    "SYMBOL": os.getenv("SYMBOL", "BTC_USDT"),          # format futures: BTC_USDT
    "INTERVAL": os.getenv("INTERVAL", "Min1"),           # Min1, Min5, Min15, Min60, Hour4, Day1...
    "EMA_FAST": int(os.getenv("EMA_FAST", "9")),
    "EMA_SLOW": int(os.getenv("EMA_SLOW", "21")),
    "RISK_PCT_EQUITY": float(os.getenv("RISK_PCT_EQUITY", "0.01")),  # 1% par trade
    "LEVERAGE": int(os.getenv("LEVERAGE", "5")),
    "OPEN_TYPE": int(os.getenv("OPEN_TYPE", "1")),       # 1=isolated, 2=cross
    "STOP_LOSS_PCT": float(os.getenv("STOP_LOSS_PCT", "0.006")),   # 0.6%
    "TAKE_PROFIT_PCT": float(os.getenv("TAKE_PROFIT_PCT", "0.012")),# 1.2%
    "MAX_KLINES": int(os.getenv("MAX_KLINES", "400")),
    "LOOP_SLEEP_SECS": int(os.getenv("LOOP_SLEEP_SECS", "10")),
    "RECV_WINDOW": int(os.getenv("RECV_WINDOW", "30")),  # secondes (<=60)
    "LOG_DIR": os.getenv("LOG_DIR", "./logs"),
    "BASE_URL": os.getenv("MEXC_CONTRACT_BASE_URL", "https://contract.mexc.com"),
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
os.makedirs(CONFIG["LOG_DIR"], exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(CONFIG["LOG_DIR"], "bot.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

log_event = get_jsonl_logger(
    os.path.join(CONFIG["LOG_DIR"], "bot_events.jsonl"),
    max_bytes=5_000_000,
    backup_count=5,
)

# ---------------------------------------------------------------------------
# Client REST Futures (Contract)
# Signature futures: HMAC_SHA256( accessKey + reqTime + requestParamString )
# Headers: ApiKey, Request-Time (ms), Signature, Content-Type, Recv-Window
# ---------------------------------------------------------------------------
class MexcFuturesClient:
    def __init__(self, access_key: str, secret_key: str, base_url: str, recv_window: int = 30):
        self.ak = access_key
        self.sk = secret_key
        self.base = base_url.rstrip("/")
        self.recv_window = recv_window
        if not self.ak or not self.sk or self.ak == "A_METTRE" or self.sk == "B_METTRE":
            logging.warning("⚠️ Clés API non définies. Le mode réel ne fonctionnera pas.")

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
            items.append(f"{quote(k, safe='')}={quote(v, safe='')}")
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

    # ----------------------- Public -----------------------
    def get_contract_detail(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v1/contract/detail"
        params = {}
        if symbol:
            params["symbol"] = symbol
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_kline(self, symbol: str, interval: str = "Min1",
                  start: Optional[int] = None, end: Optional[int] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v1/contract/kline/{symbol}"
        params = {"interval": interval}
        if start is not None:
            params["start"] = int(start)  # en secondes
        if end is not None:
            params["end"] = int(end)      # en secondes
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.base}/api/v1/contract/ticker"
        params = {}
        if symbol:
            params["symbol"] = symbol
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    # ----------------------- Privés -----------------------
    def _private_request(self, method: str, path: str,
                         params: Optional[Dict[str, Any]] = None,
                         body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        method = method.upper()
        url = f"{self.base}{path}"
        req_ms = self._ms()

        if method in ("GET", "DELETE"):
            qs = self._urlencode_sorted(params or {})
            sig = self._sign(qs, req_ms)
            headers = self._headers(sig, req_ms)
            r = requests.request(method, url, params=params, headers=headers, timeout=20)
        elif method == "POST":
            body_str = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=False)
            sig = self._sign(body_str, req_ms)
            headers = self._headers(sig, req_ms)
            r = requests.post(url, data=body_str.encode("utf-8"), headers=headers, timeout=20)
        else:
            raise ValueError("Méthode non supportée")

        try:
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logging.error("Erreur HTTP/JSON %s %s -> %s", method, path, str(e))
            data = {"success": False, "error": str(e), "status_code": getattr(r, "status_code", None)}

        log_event("http_private", {"method": method, "path": path, "params": params, "body": body, "response": data})
        return data

    # --- Comptes & positions
    def get_assets(self) -> Dict[str, Any]:
        return self._private_request("GET", "/api/v1/private/account/assets")

    def get_positions(self) -> Dict[str, Any]:
        return self._private_request("GET", "/api/v1/private/position/list/history_positions",
                                     params={"page_num": 1, "page_size": 50})

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        return self._private_request("GET", "/api/v1/private/order/list/open_orders",
                                     params={"symbol": symbol} if symbol else None)

    # --- Ordres
    def place_order(self, symbol: str, side: int, vol: int, order_type: int,
                    price: Optional[float] = None, open_type: int = 1, leverage: Optional[int] = None,
                    position_id: Optional[int] = None, external_oid: Optional[str] = None,
                    stop_loss: Optional[float] = None, take_profit: Optional[float] = None,
                    reduce_only: Optional[bool] = None, position_mode: Optional[int] = None) -> Dict[str, Any]:
        """
        side: 1=open long, 2=close short, 3=open short, 4=close long
        type: 1=limit, 2=post-only, 3=IOC, 4=FOK, 5=market, 6=convert market to current price
        """
        if CONFIG["PAPER_TRADE"]:
            logging.info("PAPER_TRADE=True -> ordre simulé: side=%s vol=%s type=%s price=%s", side, vol, order_type, price)
            return {"success": True, "paperTrade": True, "simulated": {
                "symbol": symbol, "side": side, "vol": vol, "type": order_type, "price": price,
                "openType": open_type, "leverage": leverage, "stopLossPrice": stop_loss, "takeProfitPrice": take_profit
            }}

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

# ---------------------------------------------------------------------------
# Outils stratégie
# ---------------------------------------------------------------------------
def ema(series: List[float], window: int) -> List[float]:
    if window <= 1 or len(series) == 0:
        return series[:]
    k = 2 / (window + 1.0)
    out = []
    prev = series[0]
    out.append(prev)
    for x in series[1:]:
        prev = x * k + prev * (1 - k)
        out.append(prev)
    return out

def cross(last_fast: float, last_slow: float, prev_fast: float, prev_slow: float) -> int:
    up = prev_fast <= prev_slow and last_fast > last_slow
    down = prev_fast >= prev_slow and last_fast < last_slow
    if up: return +1
    if down: return -1
    return 0

def compute_position_size(contract_detail: Dict[str, Any], equity_usdt: float,
                          price: float, risk_pct: float, leverage: int) -> int:
    contracts = (contract_detail or {}).get("data", [])
    if not isinstance(contracts, list):
        contracts = [contract_detail.get("data")]
    c = None
    for row in contracts:
        if row and row.get("symbol") == CONFIG["SYMBOL"]:
            c = row
            break
    if not c:
        raise ValueError("Contract detail introuvable pour le symbole")

    contract_size = float(c.get("contractSize", 0.0001))
    vol_unit = int(c.get("volUnit", 1))
    min_vol = int(c.get("minVol", 1))

    notional = max(0.0, equity_usdt * float(risk_pct) * float(leverage))
    if notional <= 0.0:
        return 0
    vol = notional / (price * contract_size)
    vol = int(max(min_vol, math.floor(vol / vol_unit) * vol_unit))
    return max(min_vol, vol)

# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------
def main():
    cfg = CONFIG
    client = MexcFuturesClient(
        access_key=cfg["MEXC_ACCESS_KEY"],
        secret_key=cfg["MEXC_SECRET_KEY"],
        base_url=cfg["BASE_URL"],
        recv_window=cfg["RECV_WINDOW"],
    )

    symbol = cfg["SYMBOL"]
    interval = cfg["INTERVAL"]
    ema_fast_n = cfg["EMA_FAST"]
    ema_slow_n = cfg["EMA_SLOW"]

    logging.info("---- MEXC Futures bot démarré ----")
    logging.info("SYMBOL=%s | INTERVAL=%s | EMA=%s/%s | PAPER_TRADE=%s",
                 symbol, interval, ema_fast_n, ema_slow_n, cfg["PAPER_TRADE"])

    # Specs contrat (taille, minVol, etc.)
    contract_detail = client.get_contract_detail(symbol)
    log_event("contract_detail", contract_detail)

    # Lecture equity (USDT)
    assets = client.get_assets()
    log_event("assets", assets)
    equity_usdt = 0.0
    try:
        for row in assets.get("data", []):
            if row.get("currency") == "USDT":
                equity_usdt = float(row.get("equity", 0.0))
                break
    except Exception:
        pass
    if equity_usdt <= 0:
        logging.warning("Equity USDT non détectée, fallback symbolique à 100 USDT pour sizing.")
        equity_usdt = 100.0

    prev_fast = prev_slow = None
    current_pos = 0  # +1 long, -1 short, 0 flat

    while True:
        try:
            k = client.get_kline(symbol, interval=interval)
            if not (k and k.get("success") and "data" in k and "close" in k["data"]):
                logging.warning("Réponse klines inattendue: %s", k)
                time.sleep(cfg["LOOP_SLEEP_SECS"]); continue

            closes = k["data"]["close"][-cfg["MAX_KLINES"]:]
            if len(closes) < max(ema_fast_n, ema_slow_n) + 2:
                logging.info("Pas assez d’historique pour EMA; retry...")
                time.sleep(cfg["LOOP_SLEEP_SECS"]); continue

            efull = ema(closes, ema_fast_n)
            eslow = ema(closes, ema_slow_n)
            last_fast, prev_fast = efull[-1], efull[-2]
            last_slow, prev_slow = eslow[-1], eslow[-2]
            x = cross(last_fast, last_slow, prev_fast, prev_slow)

            tick = client.get_ticker(symbol)
            if not (tick and tick.get("success") and tick.get("data")):
                logging.warning("Ticker vide: %s", tick)
                time.sleep(cfg["LOOP_SLEEP_SECS"]); continue
            tdata = tick["data"]
            if isinstance(tdata, list):
                price = None
                for row in tdata:
                    if row.get("symbol") == symbol:
                        price = float(row.get("lastPrice")); break
                if price is None:
                    logging.warning("Prix introuvable pour %s", symbol)
                    time.sleep(cfg["LOOP_SLEEP_SECS"]); continue
            else:
                price = float(tdata.get("lastPrice"))

            vol = compute_position_size(contract_detail, equity_usdt, price,
                                        cfg["RISK_PCT_EQUITY"], cfg["LEVERAGE"])
            if vol <= 0:
                logging.info("vol calculé = 0; on attend.")
                time.sleep(cfg["LOOP_SLEEP_SECS"]); continue

            sl_long = price * (1.0 - cfg["STOP_LOSS_PCT"])
            tp_long = price * (1.0 + cfg["TAKE_PROFIT_PCT"])
            sl_short = price * (1.0 + cfg["STOP_LOSS_PCT"])
            tp_short = price * (1.0 - cfg["TAKE_PROFIT_PCT"])

            log_event("signal", {"fast": last_fast, "slow": last_slow, "cross": x,
                                 "price": price, "pos": current_pos, "vol": vol})

            # type=5 (market). On passe "price" à titre conservateur.
            if x == +1 and current_pos <= 0:
                if current_pos < 0:
                    client.place_order(symbol, side=4, vol=vol, order_type=5, price=price,
                                       open_type=CONFIG["OPEN_TYPE"], leverage=CONFIG["LEVERAGE"], reduce_only=True)
                    current_pos = 0; time.sleep(0.3)
                resp = client.place_order(symbol, side=1, vol=vol, order_type=5, price=price,
                                          open_type=CONFIG["OPEN_TYPE"], leverage=CONFIG["LEVERAGE"],
                                          stop_loss=sl_long, take_profit=tp_long)
                log_event("order_long", resp)
                logging.info("→ LONG vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
                             vol, price, sl_long, tp_long, "paper" if CONFIG["PAPER_TRADE"] else "live")
                current_pos = +1

            elif x == -1 and current_pos >= 0:
                if current_pos > 0:
                    client.place_order(symbol, side=2, vol=vol, order_type=5, price=price,
                                       open_type=CONFIG["OPEN_TYPE"], leverage=CONFIG["LEVERAGE"], reduce_only=True)
                    current_pos = 0; time.sleep(0.3)
                resp = client.place_order(symbol, side=3, vol=vol, order_type=5, price=price,
                                          open_type=CONFIG["OPEN_TYPE"], leverage=CONFIG["LEVERAGE"],
                                          stop_loss=sl_short, take_profit=tp_short)
                log_event("order_short", resp)
                logging.info("→ SHORT vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
                             vol, price, sl_short, tp_short, "paper" if CONFIG["PAPER_TRADE"] else "live")
                current_pos = -1

            time.sleep(cfg["LOOP_SLEEP_SECS"])

        except KeyboardInterrupt:
            logging.info("Arrêt manuel.")
            break
        except Exception as e:
            logging.exception("Erreur boucle principale: %s", str(e))
            time.sleep(3)

if __name__ == "__main__":
    main()
