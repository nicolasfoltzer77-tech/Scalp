#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bitget USDT-M futures trading bot."""
import argparse
import logging
import os
import time
from typing import Any, Dict, Optional, List

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
from scalp.strategy import ema, cross
from scalp.trade_utils import (
    compute_position_size,
    analyse_risque,
    trailing_stop,
    should_scale_in,
    timeout_exit,
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
            try:
                eq = float(a.get("equity", a.get("available", 0)) or 0)
            except Exception:
                eq = 0.0
            norm.append({**a, "currency": cur, "equity": eq})
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


def send_selected_pairs(client: Any, top_n: int = 20) -> Dict[str, str]:
    """Send the selected trading pairs and return the payload."""
    payload = _pairs.send_selected_pairs(
        client,
        top_n=top_n,
        select_fn=filter_trade_pairs,
        notify_fn=notify,
    )
    return payload


def update(client: Any, top_n: int = 20) -> Dict[str, str]:
    """Send a fresh list of pairs to reflect current market conditions."""
    payload = send_selected_pairs(client, top_n=top_n)
    text = _format_text("pair_list", payload)
    logging.info(text)
    return payload


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
    risk_mgr = RiskManager(
        max_daily_loss_pct=cfg["MAX_DAILY_LOSS_PCT"],
        max_daily_profit_pct=cfg["MAX_DAILY_PROFIT_PCT"],
        max_positions=cfg["MAX_POSITIONS"],
        risk_pct=cfg["RISK_PCT_EQUITY"],
    )

    # Ensure a clean state: cancel lingering orders and close leftover positions
    try:
        open_orders = client.get_open_orders(cfg["SYMBOL"])
        if open_orders.get("data"):
            logging.info("Annulation des ordres ouverts au démarrage")
            client.cancel_all(cfg["SYMBOL"], margin_coin=cfg["MARGIN_COIN"])
    except Exception as exc:  # pragma: no cover - best effort
        logging.error("Erreur annulation ordres ouverts: %s", exc)
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
    except requests.HTTPError as exc:  # pragma: no cover - network issues
        logging.error("Erreur r\u00e9cup\u00e9ration contract detail: %s", exc)
        contract_detail = {"success": False, "code": 404}
    log_event("contract_detail", contract_detail)

    assets = client.get_assets()
    log_event("assets", assets)
    equity_usdt = 0.0
    try:
        for row in assets.get("data", []):
            if row.get("currency") == "USDT":
                for key in ("equity", "usdtEquity", "available", "cashBalance"):
                    val = row.get(key)
                    try:
                        if val is not None:
                            equity_usdt = float(val)
                    except (TypeError, ValueError):
                        equity_usdt = 0.0
                    if equity_usdt > 0:
                        break
                break
    except Exception:
        pass
    if equity_usdt <= 0:
        logging.warning(
            "Equity USDT non détectée, fallback symbolique à 100 USDT pour sizing."
        )
        equity_usdt = 100.0

    prev_fast = prev_slow = None
    current_pos = 0
    entry_price = None
    entry_time = None
    stop_long = stop_short = None
    take_profit = None
    session_pnl = 0.0
    last_entry_price = None

    def close_position(side: int, price: float, vol: int) -> bool:
        nonlocal current_pos, entry_price, entry_time, session_pnl, equity_usdt, stop_long, stop_short, take_profit
        pnl = round(calc_pnl_pct(entry_price, price, side, fee_rate), 2)
        payload = {
            "side": "long" if side > 0 else "short",
            "symbol": symbol,
            "entry": entry_price,
            "exit": price,
            "pnl_usd": round((price - entry_price) * vol, 2)
            if side > 0
            else round((entry_price - price) * vol, 2),
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
            reduce_only=True,
        )
        equity_usdt *= 1 + pnl / 100.0
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
        entry_price = None
        entry_time = None
        stop_long = stop_short = None
        take_profit = None
        last_entry_price = None
        time.sleep(0.3)
        return kill

    notify("bot_started")
    try:
        update(client, top_n=20)
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
                update(client, top_n=20)
            except Exception as exc:  # pragma: no cover - network
                logging.error("Erreur update marché: %s", exc)
            next_update = now + 60

        try:
            if current_pos == 0:
                pairs = filter_trade_pairs(client, top_n=20)
                signals = find_trade_positions(
                    client,
                    pairs,
                    ema_fast_n=ema_fast_n,
                    ema_slow_n=ema_slow_n,
                )
                if signals:
                    next_symbol = signals[0].get("symbol")
                    if next_symbol and next_symbol != symbol:
                        symbol = next_symbol
                        try:
                            contract_detail = client.get_contract_detail(symbol)
                        except requests.HTTPError as exc:  # pragma: no cover - network
                            logging.error(
                                "Erreur récupération contract detail: %s", exc
                            )
                            contract_detail = {"success": False, "code": 404}
                        log_event("contract_detail", contract_detail)
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
                            price = float(price_str)
                        break
                if price is None:
                    logging.warning("Prix introuvable pour %s", symbol)
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
            else:
                price_str = tdata.get("lastPr") or tdata.get("lastPrice")
                price = float(price_str)

            vol_close = compute_position_size(
                contract_detail,
                equity_usdt,
                price,
                risk_mgr.risk_pct,
                cfg["LEVERAGE"],
                symbol,
            )
            if vol_close <= 0:
                logging.info("vol calculé = 0; on attend.")
                time.sleep(cfg["LOOP_SLEEP_SECS"])
                continue
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
                    vol_add = compute_position_size(
                        contract_detail,
                        equity_usdt,
                        price,
                        risk_mgr.risk_pct,
                        cfg["LEVERAGE"],
                        symbol,
                    )
                    if vol_add > 0:
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
                    vol_add = compute_position_size(
                        contract_detail,
                        equity_usdt,
                        price,
                        risk_mgr.risk_pct,
                        cfg["LEVERAGE"],
                        symbol,
                    )
                    if vol_add > 0:
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
                    "sl_usd": round((price - sl_long) * vol_open, 2),
                    "tp_usd": round((tp_long - price) * vol_open, 2),
                    "fee_rate": fee_rate,
                    "session_pnl": session_pnl,
                }
                log_event("position_opened", open_payload)
                notify("position_opened", open_payload)
                current_pos = +1
                entry_price = price
                entry_time = now_ts
                stop_long = sl_long
                stop_short = None
                take_profit = tp_long
                last_entry_price = entry_price

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
                    "sl_usd": round((sl_short - price) * vol_open, 2),
                    "tp_usd": round((price - tp_short) * vol_open, 2),
                    "fee_rate": fee_rate,
                    "session_pnl": session_pnl,
                }
                log_event("position_opened", open_payload)
                notify("position_opened", open_payload)
                current_pos = -1
                entry_price = price
                entry_time = now_ts
                stop_short = sl_short
                stop_long = None
                take_profit = tp_short
                last_entry_price = entry_price

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
    except requests.HTTPError as exc:  # pragma: no cover - network issues
        logging.error("Erreur HTTP principale: %s", exc)
