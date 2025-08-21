#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bitget USDT-M futures trading bot."""
import argparse
import logging
import os
import time
from typing import Any, Dict, Optional, List

import requests

from scalp.logging_utils import get_jsonl_logger, TradeLogger
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
    critical = {"BITGET_ACCESS_KEY", "BITGET_SECRET_KEY"}
    for key in critical:
        val = os.getenv(key)
        if not val or val in {"", "A_METTRE", "B_METTRE"}:
            logging.warning("%s manquante", key)


class BitgetFuturesClient(_BaseBitgetFuturesClient):
    """Wrapper injecting the ``requests`` module and logger."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("requests_module", requests)
        kwargs.setdefault("log_event", log_event)
        super().__init__(*args, **kwargs)


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


def send_selected_pairs(
    client: Any, top_n: int = 20, tg_bot: Any | None = None
) -> Dict[str, str]:
    """Send the selected trading pairs and return the payload."""
    payload = _pairs.send_selected_pairs(
        client,
        top_n=top_n,
        select_fn=filter_trade_pairs,
        notify_fn=notify,
    )
    if tg_bot and payload:
        tg_bot.send(_format_text("pair_list", payload))
    return payload


def update(client: Any, top_n: int = 20, tg_bot: Any | None = None) -> Dict[str, str]:
    """Send a fresh list of pairs to reflect current market conditions."""
    payload = send_selected_pairs(client, top_n=top_n, tg_bot=tg_bot)
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
            client.cancel_all(cfg["SYMBOL"])
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
                equity_usdt = float(row.get("equity", 0.0))
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
        send_selected_pairs(client, top_n=20, tg_bot=tg_bot)
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
                update(client, top_n=20, tg_bot=tg_bot)
            except Exception as exc:  # pragma: no cover - network
                logging.error("Erreur update marché: %s", exc)
            next_update = now + 60

        try:
            k = client.get_kline(symbol, interval=interval)
            if not (k and k.get("success") and "data" in k and "close" in k["data"]):
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
            if not (tick and tick.get("success") and tick.get("data")):
                logging.warning("Ticker vide: %s", tick)
                time.sleep(cfg["LOOP_SLEEP_SECS"])
                continue
            tdata = tick["data"]
            if isinstance(tdata, list):
                price = None
                for row in tdata:
                    if row.get("symbol") == symbol:
                        price = float(row.get("lastPrice"))
                        break
                if price is None:
                    logging.warning("Prix introuvable pour %s", symbol)
                    time.sleep(cfg["LOOP_SLEEP_SECS"])
                    continue
            else:
                price = float(tdata.get("lastPrice"))

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
                    "→ LONG vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
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
                    "→ SHORT vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
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
