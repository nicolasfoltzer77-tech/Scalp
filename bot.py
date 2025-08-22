#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bitget USDT-M futures trading bot."""
import argparse
import logging
import os
import time
from typing import Any, Dict, Optional, List, Tuple

import requests

from scalp.logging_utils import (
    get_jsonl_logger,
    TradeLogger,
    log_position,
    log_operation_memo,
)
from scalp.metrics import calc_pnl_pct, calc_atr
from scalp.notifier import notify, _format_text
from scalp import __version__, RiskManager
from scalp.telegram_bot import init_telegram_bot

from scalp.bot_config import CONFIG
from scalp.strategy import ema, cross, generate_signal, Signal
from scalp.trade_utils import (
    compute_position_size,
    analyse_risque,
    trailing_stop,
    should_scale_in,
    timeout_exit,
    extract_available_balance,
)
from scalp import pairs as _pairs
from scalp.backtest import backtest_trades  # noqa: F401
from scalp.bitget_client import BitgetFuturesClient as _BaseBitgetFuturesClient

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
os.makedirs(CONFIG["LOG_DIR"], exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(CONFIG["LOG_DIR"], "bot.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def _noop_event(*_: Any, **__: Any) -> None:
    pass


log_event = _noop_event


def check_config() -> None:
    """Log only missing critical environment variables."""
    critical = {"BITGET_ACCESS_KEY", "BITGET_SECRET_KEY", "BITGET_PASSPHRASE"}
    for key in critical:
        val = os.getenv(key)
        if not val or val in {"", "A_METTRE", "B_METTRE"}:
            logging.warning("%s manquante", key)


class BitgetFuturesClient(_BaseBitgetFuturesClient):
    """Wrapper injectant ``requests`` + normalisations pour le bot."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("requests_module", requests)
        kwargs.setdefault("log_event", log_event)
        super().__init__(*args, **kwargs)

    # --------- assets (\u00e9quity USDT) via endpoint priv\u00e9 -----------------------
    def get_assets(self) -> Dict[str, Any]:
        # Le client de base expose _private_request ; on l'utilise ici.
        # GET /api/v2/mix/account/accounts?productType=...&marginCoin=USDT
        params = {"productType": self.product_type, "marginCoin": "USDT"}
        resp = self._private_request("GET", "/api/v2/mix/account/accounts", params=params)
        rows = resp.get("data", []) or []
        if not isinstance(rows, list):
            rows = [rows]
        # normalisation pour que bot.py trouve currency/equity
        norm = []
        for a in rows:
            cur = a.get("marginCoin") or a.get("currency") or "USDT"

            # Bitget peut retourner plusieurs clés différentes pour la marge
            # disponible.  On tente en priorité ``available`` mais on supporte
            # aussi ``availableBalance`` et ``availableMargin``.  Si aucune de
            # ces clés n'est présente on se replie sur ``cashBalance`` puis sur
            # les métriques d'équité totale.
            available = None
            for key in ("available", "availableBalance", "availableMargin", "cashBalance"):
                val = a.get(key)
                if val is None:
                    continue
                try:
                    available = float(val) or 0.0
                except Exception:  # pragma: no cover - cas rare
                    available = 0.0
                break

            if available is None:
                for key in ("equity", "usdtEquity"):
                    val = a.get(key)
                    if val is None:
                        continue
                    try:
                        available = float(val) or 0.0
                    except Exception:  # pragma: no cover - cas rare
                        available = 0.0
                    break

            if available is None:
                available = 0.0

            norm.append({**a, "currency": cur, "equity": available, "available": available})

        return {"code": resp.get("code", "00000"), "data": norm, "success": True}

    # --------- tickers publics + normalisation champs ------------------------
    def get_ticker(self, symbol: str | None = None) -> Dict[str, Any]:
        base = self.base.rstrip("/")
        if symbol:
            url = f"{base}/api/v2/mix/market/ticker"
            params = {"symbol": symbol.replace("_", ""), "productType": self.product_type}
        else:
            url = f"{base}/api/v2/mix/market/tickers"
            params = {"productType": self.product_type}

        r = self.requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", []) or []
        if not isinstance(rows, list):
            rows = [rows]

        norm = []
        for row in rows:
            d = dict(row)
            # cl\u00e9s compatibles avec scalp/pairs.py
            d["symbol"] = d.get("symbol") or d.get("instId")
            d["lastPrice"] = d.get("lastPr") or d.get("lastPrice")
            d["bidPrice"] = d.get("bestBidPrice") or d.get("bidPr") or d.get("bidPrice")
            d["askPrice"] = d.get("bestAskPrice") or d.get("askPr") or d.get("askPrice")
            vol = (
                d.get("usdtVolume")
                or d.get("quoteVolume")
                or d.get("baseVolume")
                or d.get("volume")
                or 0
            )
            try:
                d["volume"] = float(vol)
            except Exception:
                d["volume"] = 0.0
            norm.append(d)
        return {"success": True, "data": norm}


# Re-export pair utilities with ability to monkeypatch ``ema``/``cross`` ---------
get_trade_pairs = _pairs.get_trade_pairs
filter_trade_pairs = _pairs.filter_trade_pairs
select_top_pairs = _pairs.select_top_pairs


def find_trade_positions(
    client: Any,
    pairs: List[Dict[str, Any]],
    *,
    interval: str = "1m",
    ema_fast_n: Optional[int] = None,
    ema_slow_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return _pairs.find_trade_positions(
        client,
        pairs,
        interval=interval,
        ema_fast_n=ema_fast_n,
        ema_slow_n=ema_slow_n,
        ema_func=ema,
        cross_func=cross,
    )


def send_selected_pairs(client: Any, top_n: int = 40) -> Dict[str, str]:
    """Send the selected trading pairs and return the payload."""
    payload = _pairs.send_selected_pairs(
        client,
        top_n=top_n,
        select_fn=filter_trade_pairs,
        notify_fn=notify,
    )
    return payload


def update(client: Any, top_n: int = 40) -> Dict[str, str]:
    """Send a fresh list of pairs to reflect current market conditions.

    ``send_selected_pairs`` performs network requests and may raise an
    exception when the exchange is unreachable.  Previously such an error
    would bubble up to the caller and could stop the bot.  The function now
    guards the call so that a failure simply results in an empty payload while
    logging the error, allowing the rest of the bot to continue running.
    """

    try:
        payload = send_selected_pairs(client, top_n=top_n)
    except Exception as exc:  # pragma: no cover - best effort
        logging.error("Erreur sélection paires: %s", exc)
        payload = {}

    text = _format_text("pair_list", payload)
    logging.info(text)
    return payload


# ---------------------------------------------------------------------------
# Helpers "safe" locaux (pas d'appel réseau)
# ---------------------------------------------------------------------------
def _safe_extract_contract_fields(contract_detail, symbol: str | None = None):
    data = contract_detail.get("data") if isinstance(contract_detail, dict) else None
    contract: Dict[str, Any] = {}
    if isinstance(data, list):
        if symbol:
            contract = next((c for c in data if c.get("symbol") == symbol), data[0] if data else {})
        else:
            contract = data[0] if data else {}
    elif isinstance(data, dict):
        contract = data
    size = contract.get("contractSize") or contract.get("sizeMultiplier") or 1.0
    min_trade = contract.get("minTradeUSDT") or contract.get("minTradeNum") or 1.0
    try:
        size_mult = float(size)
    except (TypeError, ValueError):
        size_mult = 1.0
    try:
        min_trade_val = float(min_trade)
    except (TypeError, ValueError):
        min_trade_val = 1.0
    return size_mult, min_trade_val


def _estimate_margin(contract_detail, price, vol, leverage):
    size_mult, _ = _safe_extract_contract_fields(contract_detail)
    notional = float(vol) * size_mult * float(price)
    lev = max(1.0, float(leverage) or 1.0)
    margin = notional / lev
    return notional, margin


def map_score_to_sig_level(score: float) -> int:
    if score < 35:
        return 1
    if score < 70:
        return 2
    return 3


RISK_MULTIPLIER = {
    1: {1: 0.6, 2: 0.8, 3: 1.0},
    2: {1: 0.8, 2: 1.0, 3: 1.25},
    3: {1: 1.0, 2: 1.25, 3: 1.5},
}

LEVERAGE_MULTIPLIER = {1: 0.5, 2: 0.75, 3: 1.0}

NOTIONAL_CAP = {
    1: {1: 0.15, 2: 0.25, 3: 0.35},
    2: {1: 0.25, 2: 0.40, 3: 0.55},
    3: {1: 0.35, 2: 0.55, 3: 0.75},
}

RISK_COLOR = {1: "\U0001F7E2", 2: "\U0001F7E1", 3: "\U0001F534"}


def compute_risk_params(sig_level: int, user_level: int, base_risk_pct: float, base_leverage: int) -> Tuple[float, int, float]:
    risk_mult = RISK_MULTIPLIER.get(sig_level, {}).get(user_level, 1.0)
    lev_key = min(sig_level, user_level)
    lev_mult = LEVERAGE_MULTIPLIER.get(lev_key, 1.0)
    risk_pct_eff = base_risk_pct * risk_mult
    leverage_eff = max(1, int(base_leverage * lev_mult))
    cap_ratio = NOTIONAL_CAP.get(user_level, {}).get(sig_level, 1.0)
    return risk_pct_eff, leverage_eff, cap_ratio


def prepare_order(
    sig: Signal,
    contract_detail: Dict[str, Any],
    equity_usdt: float,
    available_usdt: float,
    base_leverage: int,
    risk_mgr: Any,
    user_risk_level: int,
) -> Dict[str, Any]:
    score = float(sig.score or 0.0)
    sig_level = map_score_to_sig_level(score)
    risk_pct_eff, leverage_eff, cap_ratio = compute_risk_params(
        sig_level, user_risk_level, risk_mgr.risk_pct, base_leverage
    )

    data = contract_detail.get("data") or []
    if isinstance(data, list):
        contract = next((c for c in data if c.get("symbol") == sig.symbol), data[0] if data else {})
    else:
        contract = data
    contract_size = float(contract.get("contractSize") or contract.get("sizeMultiplier") or 0.0001)
    vol_unit = int(contract.get("volUnit", 1))
    min_vol = int(contract.get("minVol", 1))
    min_usdt = float(contract.get("minTradeUSDT", 5))
    max_lev = int(contract.get("maxLever") or contract.get("maxLeverage") or leverage_eff)
    leverage_eff = min(leverage_eff, max_lev)

    vol = compute_position_size(
        contract_detail,
        equity_usdt=equity_usdt,
        price=sig.price,
        risk_pct=risk_pct_eff,
        leverage=leverage_eff,
        symbol=sig.symbol,
        available_usdt=available_usdt,
    )
    vol_before = vol

    denom = sig.price * contract_size
    notional = vol * denom

    cap_notional = cap_ratio * available_usdt
    if cap_notional > 0 and notional > cap_notional:
        vol = int((cap_notional / denom) // vol_unit * vol_unit)
        notional = vol * denom

    fee_rate = max(CONFIG.get("FEE_RATE", 0.0), 0.001)
    required_margin = (notional / leverage_eff + fee_rate * notional) * 1.03
    if required_margin > available_usdt:
        max_notional = available_usdt / ((1 / leverage_eff + fee_rate) * 1.03)
        vol_cap = int((max_notional / denom) // vol_unit * vol_unit)
        vol = min(vol, vol_cap)
        notional = vol * denom
        required_margin = (notional / leverage_eff + fee_rate * notional) * 1.03

    if vol < min_vol or notional < min_usdt:
        vol = 0
        notional = 0.0
        required_margin = 0.0

    return {
        "vol": int(vol),
        "vol_before": int(vol_before),
        "leverage_eff": int(leverage_eff),
        "risk_pct_eff": risk_pct_eff,
        "sig_level": sig_level,
        "score": score,
        "risk_color": RISK_COLOR.get(sig_level, ""),
        "notional": notional,
        "required_margin": required_margin,
        "cap_ratio": cap_ratio,
    }


def attempt_entry(
    client: Any,
    contract_detail: Dict[str, Any],
    sig: Signal,
    equity_usdt: float,
    available_usdt: float,
    cfg: Dict[str, Any],
    risk_mgr: Any,
    user_risk_level: int,
) -> Dict[str, Any]:
    params = prepare_order(
        sig,
        contract_detail,
        equity_usdt,
        available_usdt,
        cfg["LEVERAGE"],
        risk_mgr,
        user_risk_level,
    )
    payload = {
        "symbol": sig.symbol,
        "side": sig.side,
        "price": sig.price,
        "available": available_usdt,
        "user_level": user_risk_level,
        **params,
    }
    notify("order_attempt", payload)
    if params["vol"] <= 0:
        return params
    side_int = 1 if sig.side == "long" else 3
    resp = client.place_order(
        sig.symbol,
        side=side_int,
        vol=params["vol"],
        order_type=5,
        price=sig.price,
        open_type=CONFIG["OPEN_TYPE"],
        leverage=params["leverage_eff"],
        stop_loss=sig.sl,
        take_profit=sig.tp1,
    )
    log_event("order", resp)
    open_payload = {
        "side": sig.side,
        "symbol": sig.symbol,
        "price": sig.price,
        "vol": params["vol"],
        "vol_before": params.get("vol_before"),
        "leverage": params["leverage_eff"],
        "risk_color": params["risk_color"],
        "sig_level": params["sig_level"],
        "score": params["score"],
        "risk_pct_eff": params["risk_pct_eff"],
        "leverage_eff": params["leverage_eff"],
        "notional": params["notional"],
        "required_margin": params["required_margin"],
        "available": available_usdt,
        "user_level": user_risk_level,
        "amount_usdt": params["notional"],
    }
    notify("position_opened", open_payload)
    return params


# ---------------------------------------------------------------------------
# Main trading loop
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Bitget USDT-M futures trading bot")
    parser.add_argument("--log-json", action="store_true", help="Enable JSON event logs")
    args = parser.parse_args(argv)

    cfg = CONFIG
    global log_event
    if args.log_json:
        log_event = get_jsonl_logger(
            os.path.join(cfg["LOG_DIR"], "bot_events.jsonl"),
            max_bytes=5_000_000,
            backup_count=5,
        )
    check_config()
    client = BitgetFuturesClient(
        access_key=cfg["BITGET_ACCESS_KEY"],
        secret_key=cfg["BITGET_SECRET_KEY"],
        base_url=cfg["BASE_URL"],
        product_type=cfg["PRODUCT_TYPE"],
        recv_window=cfg["RECV_WINDOW"],
        paper_trade=cfg["PAPER_TRADE"],
        passphrase=cfg.get("BITGET_PASSPHRASE"),
    )
    base_risk = min(
        max(cfg["RISK_PCT_EQUITY"], cfg["RISK_PCT_MIN"]),
        cfg["RISK_PCT_MAX"],
    )
    risk_mgr = RiskManager(
        max_daily_loss_pct=cfg["MAX_DAILY_LOSS_PCT"],
        max_daily_profit_pct=cfg["MAX_DAILY_PROFIT_PCT"],
        max_positions=cfg["MAX_POSITIONS"],
        risk_pct=base_risk,
    )

    # Ensure a clean state: close leftover positions
    try:
        positions = client.get_positions(product_type=cfg["PRODUCT_TYPE"])
        if positions.get("data"):
            logging.info("Fermeture des positions ouvertes au démarrage")
            client.close_all_positions(product_type=cfg["PRODUCT_TYPE"])
    except Exception as exc:  # pragma: no cover - best effort
        logging.error("Erreur fermeture positions existantes: %s", exc)

    trade_logger = TradeLogger(
        os.path.join(cfg["LOG_DIR"], "trades.csv"),
        os.path.join(cfg["LOG_DIR"], "trades.sqlite"),
    )

    tg_bot = init_telegram_bot(client, cfg, risk_mgr)

    symbol = cfg["SYMBOL"]
    interval = cfg["INTERVAL"]
    ema_fast_n = cfg["EMA_FAST"]
    ema_slow_n = cfg["EMA_SLOW"]
    fee_rate = cfg.get("FEE_RATE", 0.0)

    try:
        contract_detail = client.get_contract_detail(symbol)
    except requests.RequestException as exc:  # pragma: no cover - network issues
        logging.error("Erreur r\u00e9cup\u00e9ration contract detail: %s", exc)
        contract_detail = {"success": False, "code": 404}
    log_event("contract_detail", contract_detail)

    def _fetch_equity() -> float:
        """Retrieve available USDT balance from the exchange.

        Bitget returns several balance metrics; ``available``/``cashBalance``
        represent free margin and are therefore preferred over total equity.
        ``0.0`` is returned when no usable balance can be obtained.
        """

        try:
            assets = client.get_assets()
            log_event("assets", assets)
        except requests.RequestException as exc:  # pragma: no cover - network issues
            logging.error("Erreur récupération assets: %s", exc)
            return 0.0

        return extract_available_balance(assets)

    equity_usdt = _fetch_equity()
    if equity_usdt <= 0:
        logging.warning(
            "Aucun solde USDT disponible; en attente de fonds avant de trader."
        )

    prev_fast = prev_slow = None
    current_pos = 0
    current_vol = 0
    entry_price = None
    entry_time = None
    stop_long = stop_short = None
    take_profit = None
    session_pnl = 0.0
    last_entry_price = None
    open_positions: set[str] = set()

    def log_bitget_positions() -> None:
        try:
            resp = client.get_positions(product_type=cfg["PRODUCT_TYPE"])
            symbols = {p.get("symbol") for p in resp.get("data", [])}
            logging.info("Positions Bitget: %s", sorted(symbols))
            log_event("bitget_positions", {"positions": list(symbols)})
            missing = open_positions - symbols
            extra = symbols - open_positions
            if missing or extra:
                log_event(
                    "open_positions_mismatch",
                    {"bot_only": list(missing), "exchange_only": list(extra)},
                )
        except Exception as exc:  # pragma: no cover - network
            logging.warning("Impossible de récupérer les positions Bitget: %s", exc)

    def close_position(side: int, price: float, vol: int) -> bool:
        nonlocal current_pos, current_vol, entry_price, entry_time, session_pnl, equity_usdt, stop_long, stop_short, take_profit
        pnl = round(calc_pnl_pct(entry_price, price, side, fee_rate), 2)
        size_mult, _ = _safe_extract_contract_fields(contract_detail, symbol)
        diff = price - entry_price
        pnl_usd = round((diff if side > 0 else -diff) * size_mult * vol, 2)
        payload = {
            "side": "long" if side > 0 else "short",
            "symbol": symbol,
            "entry": entry_price,
            "exit": price,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl,
            "fee_pct": fee_rate * 2 * 100,
        }
        log_event("position_closed", payload)
        session_pnl += pnl
        payload["session_pnl"] = session_pnl
        notify("position_closed", payload)
        client.place_order(
            symbol,
            side=4 if side > 0 else 2,
            vol=vol,
            order_type=5,
            price=price,
            open_type=CONFIG["OPEN_TYPE"],
            leverage=CONFIG["LEVERAGE"],
        )
        new_eq = _fetch_equity()
        equity_usdt = new_eq
        risk_mgr.record_trade(pnl)
        logging.info("Nouveau risk_pct: %.4f", risk_mgr.risk_pct)
        kill = risk_mgr.kill_switch
        if kill:
            logging.warning("Kill switch activé, arrêt du bot.")
        pause = risk_mgr.pause_duration()
        if pause:
            logging.info("Pause %s s après série de pertes", pause)
            time.sleep(pause)
        trade_logger.log(
            {
                "pair": symbol,
                "tf": interval,
                "dir": "long" if side > 0 else "short",
                "entry": entry_price,
                "sl": stop_long if side > 0 else stop_short,
                "tp": take_profit,
                "score": None,
                "reasons": None,
                "pnl": pnl,
            }
        )
        log_position(
            {
                "timestamp": int(time.time()),
                "pair": symbol,
                "direction": "long" if side > 0 else "short",
                "entry": entry_price,
                "exit": price,
                "pnl_pct": pnl,
                "fee_rate": fee_rate,
                "notes": None,
            }
        )
        log_operation_memo(
            {
                "timestamp": int(time.time()),
                "pair": symbol,
                "details": f"Closed with pnl {pnl}%",
            }
        )
        current_pos = 0
        current_vol = 0
        entry_price = None
        entry_time = None
        stop_long = stop_short = None
        take_profit = None
        last_entry_price = None
        if symbol in open_positions:
            open_positions.remove(symbol)
            logging.info("Positions ouvertes: %s", sorted(open_positions))
            log_event("open_positions", {"positions": list(open_positions)})
        else:
            logging.warning("Fermeture d'une position non suivie: %s", symbol)
            logging.info("Positions ouvertes: %s", sorted(open_positions))
            log_event(
                "open_positions",
                {"positions": list(open_positions), "missing": symbol},
            )
        log_bitget_positions()
        time.sleep(0.3)
        return kill

    notify("bot_started")
    try:
        update(client, top_n=40)
    except Exception as exc:  # pragma: no cover - network
        logging.error("Erreur sélection paires: %s", exc)
    if tg_bot:
        tg_bot.send_main_menu(0.0)
    next_update = time.time() + 60
    while True:
        if tg_bot:
            try:
                tg_bot.handle_updates(session_pnl)
                if getattr(tg_bot, "stop_requested", False):
                    break
            except Exception as exc:  # pragma: no cover - robustness
                logging.error("Erreur commandes Telegram: %s", exc)

        now = time.time()
        if now >= next_update:
            try:
                update(client, top_n=40)
            except Exception as exc:  # pragma: no cover - network
                logging.error("Erreur update marché: %s", exc)
            next_update = now + 60

        try:
            new_eq = _fetch_equity()
            equity_usdt = new_eq
            if current_pos == 0:
                pairs = filter_trade_pairs(client, top_n=40)
                signals = find_trade_positions(
                    client,
                    pairs,
                    ema_fast_n=ema_fast_n,
                    ema_slow_n=ema_slow_n,
                )
                if signals:
                    next_symbol = signals[0].get("symbol")
                    if next_symbol and next_symbol != symbol:
                        # Liste blanche
                        allowed = set(cfg.get("ALLOWED_SYMBOLS") or [])
                        if allowed and next_symbol not in allowed:
                            logging.info(
                                "Symbole %s non autorisé par ALLOWED_SYMBOLS -> ignoré",
                                next_symbol,
                            )
                            time.sleep(cfg["LOOP_SLEEP_SECS"])
                            continue
                        symbol = next_symbol
                        try:
                            contract_detail = client.get_contract_detail(symbol)
                        except requests.RequestException as exc:  # pragma: no cover - network
                            logging.error(
                                "Erreur récupération contract detail: %s", exc
                            )
                            contract_detail = {"success": False, "code": 404}
                        log_event("contract_detail", contract_detail)
                        ok_contract = (
                            contract_detail.get("success") is True
                            or contract_detail.get("code") == "00000"
                        )
                        if not ok_contract:
                            logging.warning(
                                "Contrat invalide pour %s -> on le saute", symbol
                            )
                            time.sleep(cfg["LOOP_SLEEP_SECS"])
                            continue
                else:
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
            k = client.get_kline(symbol, interval=interval)
            ok = False
            if k:
                code = k.get("code")
                ok = (k.get("success") is True) or (isinstance(code, str) and code == "00000")
            if not (ok and "data" in k and "close" in k["data"]):
                logging.warning("Réponse klines inattendue: %s", k)
                time.sleep(cfg["LOOP_SLEEP_SECS"])
                continue

            data = k["data"]
            closes = data["close"][-cfg["MAX_KLINES"]:]
            highs = data["high"][-cfg["MAX_KLINES"]:]
            lows = data["low"][-cfg["MAX_KLINES"]:]
            min_len = max(ema_fast_n, ema_slow_n, cfg["ATR_PERIOD"]) + 2
            if len(closes) < min_len:
                logging.info("Pas assez d’historique pour EMA/ATR; retry...")
                time.sleep(cfg["LOOP_SLEEP_SECS"])
                continue

            efull = ema(closes, ema_fast_n)
            eslow = ema(closes, ema_slow_n)
            last_fast, prev_fast = efull[-1], efull[-2]
            last_slow, prev_slow = eslow[-1], eslow[-2]
            x = cross(last_fast, last_slow, prev_fast, prev_slow)
            atr = calc_atr(
                highs[-(cfg["ATR_PERIOD"] + 1) :],
                lows[-(cfg["ATR_PERIOD"] + 1) :],
                closes[-(cfg["ATR_PERIOD"] + 1) :],
                period=cfg["ATR_PERIOD"],
            )

            tick = client.get_ticker(symbol)
            tdata = tick.get("data") if tick else None
            code = tick.get("code") if tick else None
            success = tick.get("success") if tick else None
            if (
                tick is None
                or (code is not None and code != "00000")
                or (success is not None and not success)
                or tdata is None
            ):
                logging.warning("Ticker vide: %s", tick)
                time.sleep(cfg["LOOP_SLEEP_SECS"])
                continue
            if hasattr(tdata, "items") and not isinstance(tdata, dict):
                tdata = dict(tdata)
            elif isinstance(tdata, list):
                tdata = [dict(r) if hasattr(r, "items") and not isinstance(r, dict) else r for r in tdata]
            if isinstance(tdata, list):
                price = None
                for row in tdata:
                    if row.get("symbol") == symbol:
                        price_str = row.get("lastPr") or row.get("lastPrice")
                        if price_str is not None:
                            try:
                                price = float(price_str)
                            except (TypeError, ValueError):
                                price = None
                        break
                if price is None:
                    logging.warning("Prix introuvable pour %s", symbol)
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
            else:
                price_str = tdata.get("lastPr") or tdata.get("lastPrice")
                try:
                    price = float(price_str)
                except (TypeError, ValueError):
                    logging.warning("Prix invalide: %s", price_str)
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue

            vol_close = current_vol
            sl_long = price * (1.0 - cfg["STOP_LOSS_PCT"])
            tp_long = price * (1.0 + cfg["TAKE_PROFIT_PCT"])
            sl_short = price * (1.0 + cfg["STOP_LOSS_PCT"])
            tp_short = price * (1.0 - cfg["TAKE_PROFIT_PCT"])

            now_ts = time.time()
            if current_pos > 0 and entry_price is not None and stop_long is not None:
                stop_long = trailing_stop(
                    "long",
                    current_price=price,
                    atr=atr,
                    sl=stop_long,
                    mult=cfg["TRAIL_ATR_MULT"],
                )
                if price <= stop_long or timeout_exit(
                    entry_time,
                    now_ts,
                    entry_price,
                    price,
                    "long",
                    progress_min=cfg["PROGRESS_MIN"],
                    timeout_min=cfg["TIMEOUT_MIN"],
                ):
                    if close_position(1, price, vol_close):
                        break
                    continue
            elif current_pos < 0 and entry_price is not None and stop_short is not None:
                stop_short = trailing_stop(
                    "short",
                    current_price=price,
                    atr=atr,
                    sl=stop_short,
                    mult=cfg["TRAIL_ATR_MULT"],
                )
                if price >= stop_short or timeout_exit(
                    entry_time,
                    now_ts,
                    entry_price,
                    price,
                    "short",
                    progress_min=cfg["PROGRESS_MIN"],
                    timeout_min=cfg["TIMEOUT_MIN"],
                ):
                    if close_position(-1, price, vol_close):
                        break
                    continue

            if (
                current_pos > 0
                and entry_price is not None
                and last_entry_price is not None
                and should_scale_in(
                    entry_price,
                    price,
                    last_entry_price,
                    atr,
                    "long",
                    distance_mult=cfg["SCALE_IN_ATR_MULT"],
                )
            ):
                positions = client.get_positions(product_type=cfg["PRODUCT_TYPE"]).get("data", [])
                if risk_mgr.can_open(len(positions)):
                    available = _fetch_equity()
                    equity_usdt = available
                    vol_pre = compute_position_size(
                        contract_detail,
                        available,
                        price,
                        risk_mgr.risk_pct,
                        cfg["LEVERAGE"],
                        symbol,
                        available_usdt=available,
                    )
                    vol_add = vol_pre
                    if cfg.get("NOTIONAL_CAP_USDT", 0) > 0:
                        size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                        vol_cap = int(cfg["NOTIONAL_CAP_USDT"] / max(1e-12, size_mult * price))
                        if vol_cap > 0:
                            vol_add = min(vol_add, vol_cap)
                    notional, margin = _estimate_margin(contract_detail, price, vol_add, cfg["LEVERAGE"])
                    max_margin = float(cfg.get("MARGIN_CAP_RATIO", 1.0)) * available
                    if margin > max_margin:
                        size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                        vol_max_afford = int((max_margin * cfg["LEVERAGE"]) / max(1e-12, size_mult * price))
                        vol_add = max(0, min(vol_add, vol_max_afford))
                        notional, margin = _estimate_margin(contract_detail, price, vol_add, cfg["LEVERAGE"])
                    size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                    taker = max(CONFIG.get("FEE_RATE", 0.0), 0.001)
                    required = (price * size_mult * vol_add / cfg["LEVERAGE"] + taker * price * size_mult * vol_add) * 1.03
                    logging.info(
                        "order_check: available=%s, required=%s, vol_pre=%s, vol_final=%s, price=%s, lev=%s, side=%s",
                        available,
                        required,
                        vol_pre,
                        vol_add,
                        price,
                        cfg["LEVERAGE"],
                        "long",
                    )
                    if vol_add <= 0:
                        logging.info("volume reduced due to margin cap")
                    else:
                        resp = client.place_order(
                            symbol,
                            side=1,
                            vol=vol_add,
                            order_type=5,
                            price=price,
                            open_type=CONFIG["OPEN_TYPE"],
                            leverage=cfg["LEVERAGE"],
                        )
                        log_event("scale_in_long", resp)
                        last_entry_price = price
                        current_vol += vol_add
            elif (
                current_pos < 0
                and entry_price is not None
                and last_entry_price is not None
                and should_scale_in(
                    entry_price,
                    price,
                    last_entry_price,
                    atr,
                    "short",
                    distance_mult=cfg["SCALE_IN_ATR_MULT"],
                )
            ):
                positions = client.get_positions(product_type=cfg["PRODUCT_TYPE"]).get("data", [])
                if risk_mgr.can_open(len(positions)):
                    available = _fetch_equity()
                    equity_usdt = available
                    vol_pre = compute_position_size(
                        contract_detail,
                        available,
                        price,
                        risk_mgr.risk_pct,
                        cfg["LEVERAGE"],
                        symbol,
                        available_usdt=available,
                    )
                    vol_add = vol_pre
                    if cfg.get("NOTIONAL_CAP_USDT", 0) > 0:
                        size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                        vol_cap = int(cfg["NOTIONAL_CAP_USDT"] / max(1e-12, size_mult * price))
                        if vol_cap > 0:
                            vol_add = min(vol_add, vol_cap)
                    notional, margin = _estimate_margin(contract_detail, price, vol_add, cfg["LEVERAGE"])
                    max_margin = float(cfg.get("MARGIN_CAP_RATIO", 1.0)) * available
                    if margin > max_margin:
                        size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                        vol_max_afford = int((max_margin * cfg["LEVERAGE"]) / max(1e-12, size_mult * price))
                        vol_add = max(0, min(vol_add, vol_max_afford))
                        notional, margin = _estimate_margin(contract_detail, price, vol_add, cfg["LEVERAGE"])
                    size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                    taker = max(CONFIG.get("FEE_RATE", 0.0), 0.001)
                    required = (price * size_mult * vol_add / cfg["LEVERAGE"] + taker * price * size_mult * vol_add) * 1.03
                    logging.info(
                        "order_check: available=%s, required=%s, vol_pre=%s, vol_final=%s, price=%s, lev=%s, side=%s",
                        available,
                        required,
                        vol_pre,
                        vol_add,
                        price,
                        cfg["LEVERAGE"],
                        "short",
                    )
                    if vol_add <= 0:
                        logging.info("volume reduced due to margin cap")
                    else:
                        resp = client.place_order(
                            symbol,
                            side=3,
                            vol=vol_add,
                            order_type=5,
                            price=price,
                            open_type=CONFIG["OPEN_TYPE"],
                            leverage=cfg["LEVERAGE"],
                        )
                        log_event("scale_in_short", resp)
                        last_entry_price = price
                        current_vol += vol_add

            log_event(
                "signal",
                {
                    "fast": last_fast,
                    "slow": last_slow,
                    "cross": x,
                    "price": price,
                    "pos": current_pos,
                    "vol": vol_close,
                },
            )

            if x == +1 and current_pos <= 0:
                if current_pos < 0 and entry_price is not None:
                    if close_position(-1, price, vol_close):
                        break

                positions = client.get_positions(product_type=cfg["PRODUCT_TYPE"]).get("data", [])
                if not risk_mgr.can_open(len(positions)):
                    logging.info("RiskManager: limites atteintes, on attend.")
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                vol_open, lev = analyse_risque(
                    contract_detail,
                    positions,
                    equity_usdt,
                    price,
                    risk_mgr.risk_pct,
                    cfg["LEVERAGE"],
                    symbol,
                    side="long",
                    risk_level=cfg.get("RISK_LEVEL", 2),
                )
                if vol_open <= 0:
                    logging.info("vol calculé = 0; on attend.")
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                available = _fetch_equity()
                equity_usdt = available
                vol_pre = compute_position_size(
                    contract_detail,
                    available,
                    price,
                    risk_mgr.risk_pct,
                    lev,
                    symbol,
                    available_usdt=available,
                )
                vol_open = min(vol_open, vol_pre)
                if cfg.get("NOTIONAL_CAP_USDT", 0) > 0:
                    size_mult, _min_trade = _safe_extract_contract_fields(contract_detail, symbol)
                    vol_cap = int(cfg["NOTIONAL_CAP_USDT"] / max(1e-12, size_mult * price))
                    if vol_cap > 0:
                        vol_open = min(vol_open, vol_cap)
                notional, margin = _estimate_margin(contract_detail, price, vol_open, lev)
                max_margin = float(cfg.get("MARGIN_CAP_RATIO", 1.0)) * available
                if margin > max_margin:
                    size_mult, _min_trade = _safe_extract_contract_fields(contract_detail, symbol)
                    vol_max_afford = int((max_margin * lev) / max(1e-12, size_mult * price))
                    vol_open = max(0, min(vol_open, vol_max_afford))
                    notional, margin = _estimate_margin(contract_detail, price, vol_open, lev)
                size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                taker = max(CONFIG.get("FEE_RATE", 0.0), 0.001)
                required = (price * size_mult * vol_open / lev + taker * price * size_mult * vol_open) * 1.03
                logging.info(
                    "order_check: available=%s, required=%s, vol_pre=%s, vol_final=%s, price=%s, lev=%s, side=%s",
                    available,
                    required,
                    vol_pre,
                    vol_open,
                    price,
                    lev,
                    "long",
                )
                if vol_open <= 0:
                    logging.info("volume reduced due to margin cap")
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                resp = client.place_order(
                    symbol,
                    side=1,
                    vol=vol_open,
                    order_type=5,
                    price=price,
                    open_type=CONFIG["OPEN_TYPE"],
                    leverage=lev,
                    stop_loss=sl_long,
                    take_profit=tp_long,
                )
                if str(resp.get("code")) != "00000":
                    log_event("order_long_error", resp)
                    logging.error("Échec ordre LONG: %s", resp)
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                log_event("order_long", resp)
                logging.info(
                    "→ LONG %s vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
                    symbol,
                    vol_open,
                    price,
                    sl_long,
                    tp_long,
                    "paper" if CONFIG["PAPER_TRADE"] else "live",
                )
                open_payload = {
                    "side": "long",
                    "symbol": symbol,
                    "price": price,
                    "vol": vol_open,
                    "leverage": CONFIG["LEVERAGE"],
                    "amount_usdt": round(price * size_mult * vol_open, 2),
                    "sl_usd": round((price - sl_long) * size_mult * vol_open, 2),
                    "tp_usd": round((tp_long - price) * size_mult * vol_open, 2),
                    "fee_rate": fee_rate,
                    "session_pnl": session_pnl,
                }
                log_event("position_opened", open_payload)
                notify("position_opened", open_payload)
                current_pos = +1
                current_vol = vol_open
                entry_price = price
                entry_time = now_ts
                stop_long = sl_long
                stop_short = None
                take_profit = tp_long
                last_entry_price = entry_price
                open_positions.add(symbol)
                logging.info("Positions ouvertes: %s", sorted(open_positions))
                log_event("open_positions", {"positions": list(open_positions)})
                log_bitget_positions()

            elif x == -1 and current_pos >= 0:
                if current_pos > 0 and entry_price is not None:
                    if close_position(1, price, vol_close):
                        break

                positions = client.get_positions(product_type=cfg["PRODUCT_TYPE"]).get("data", [])
                if not risk_mgr.can_open(len(positions)):
                    logging.info("RiskManager: limites atteintes, on attend.")
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                vol_open, lev = analyse_risque(
                    contract_detail,
                    positions,
                    equity_usdt,
                    price,
                    risk_mgr.risk_pct,
                    cfg["LEVERAGE"],
                    symbol,
                    side="short",
                    risk_level=cfg.get("RISK_LEVEL", 2),
                )
                if vol_open <= 0:
                    logging.info("vol calculé = 0; on attend.")
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                available = _fetch_equity()
                equity_usdt = available
                vol_pre = compute_position_size(
                    contract_detail,
                    available,
                    price,
                    risk_mgr.risk_pct,
                    lev,
                    symbol,
                    available_usdt=available,
                )
                vol_open = min(vol_open, vol_pre)
                if cfg.get("NOTIONAL_CAP_USDT", 0) > 0:
                    size_mult, _min_trade = _safe_extract_contract_fields(contract_detail, symbol)
                    vol_cap = int(cfg["NOTIONAL_CAP_USDT"] / max(1e-12, size_mult * price))
                    if vol_cap > 0:
                        vol_open = min(vol_open, vol_cap)
                notional, margin = _estimate_margin(contract_detail, price, vol_open, lev)
                max_margin = float(cfg.get("MARGIN_CAP_RATIO", 1.0)) * available
                if margin > max_margin:
                    size_mult, _min_trade = _safe_extract_contract_fields(contract_detail, symbol)
                    vol_max_afford = int((max_margin * lev) / max(1e-12, size_mult * price))
                    vol_open = max(0, min(vol_open, vol_max_afford))
                    notional, margin = _estimate_margin(contract_detail, price, vol_open, lev)
                size_mult, _m = _safe_extract_contract_fields(contract_detail, symbol)
                taker = max(CONFIG.get("FEE_RATE", 0.0), 0.001)
                required = (price * size_mult * vol_open / lev + taker * price * size_mult * vol_open) * 1.03
                logging.info(
                    "order_check: available=%s, required=%s, vol_pre=%s, vol_final=%s, price=%s, lev=%s, side=%s",
                    available,
                    required,
                    vol_pre,
                    vol_open,
                    price,
                    lev,
                    "short",
                )
                if vol_open <= 0:
                    logging.info("volume reduced due to margin cap")
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                resp = client.place_order(
                    symbol,
                    side=3,
                    vol=vol_open,
                    order_type=5,
                    price=price,
                    open_type=CONFIG["OPEN_TYPE"],
                    leverage=lev,
                    stop_loss=sl_short,
                    take_profit=tp_short,
                )
                if str(resp.get("code")) != "00000":
                    log_event("order_short_error", resp)
                    logging.error("Échec ordre SHORT: %s", resp)
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
                log_event("order_short", resp)
                logging.info(
                    "→ SHORT %s vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
                    symbol,
                    vol_open,
                    price,
                    sl_short,
                    tp_short,
                    "paper" if CONFIG["PAPER_TRADE"] else "live",
                )
                open_payload = {
                    "side": "short",
                    "symbol": symbol,
                    "price": price,
                    "vol": vol_open,
                    "leverage": CONFIG["LEVERAGE"],
                    "amount_usdt": round(price * size_mult * vol_open, 2),
                    "sl_usd": round((sl_short - price) * size_mult * vol_open, 2),
                    "tp_usd": round((price - tp_short) * size_mult * vol_open, 2),
                    "fee_rate": fee_rate,
                    "session_pnl": session_pnl,
                }
                log_event("position_opened", open_payload)
                notify("position_opened", open_payload)
                current_pos = -1
                current_vol = vol_open
                entry_price = price
                entry_time = now_ts
                stop_short = sl_short
                stop_long = None
                take_profit = tp_short
                last_entry_price = entry_price
                open_positions.add(symbol)
                logging.info("Positions ouvertes: %s", sorted(open_positions))
                log_event("open_positions", {"positions": list(open_positions)})
                log_bitget_positions()

            time.sleep(cfg["LOOP_SLEEP_SECS"])

        except KeyboardInterrupt:
            logging.info("Arrêt manuel.")
            break
        except Exception as e:  # pragma: no cover - safeguard
            logging.exception("Erreur boucle principale: %s", str(e))
            time.sleep(3)
    notify("bot_stopped", {"session_pnl": session_pnl})


if __name__ == "__main__":  # pragma: no cover - manual run
    try:
        main()
    except requests.RequestException as exc:  # pragma: no cover - network issues
        logging.error("Erreur HTTP principale: %s", exc)
