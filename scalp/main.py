from __future__ import annotations

import logging
import os
import sys
import time
from typing import Optional, Dict, Any

from .config import load_config, BotConfig
from .client import MexcFuturesClient
from .strategy import ema, cross, compute_position_size
from .logging_utils import get_jsonl_logger


def setup_logging(log_dir: str):
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "bot.log"), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main() -> None:
    cfg: BotConfig = load_config()
    setup_logging(cfg.LOG_DIR)
    log_event = get_jsonl_logger(
        os.path.join(cfg.LOG_DIR, "bot_events.jsonl"), max_bytes=5_000_000, backup_count=5
    )

    client = MexcFuturesClient(
        access_key=cfg.MEXC_ACCESS_KEY,
        secret_key=cfg.MEXC_SECRET_KEY,
        base_url=cfg.BASE_URL,
        recv_window=cfg.RECV_WINDOW,
        paper_trade=cfg.PAPER_TRADE,
    )

    symbol = cfg.SYMBOL
    interval = cfg.INTERVAL
    ema_fast_n = cfg.EMA_FAST
    ema_slow_n = cfg.EMA_SLOW

    logging.info("---- MEXC Futures bot démarré ----")
    logging.info(
        "SYMBOL=%s | INTERVAL=%s | EMA=%s/%s | PAPER_TRADE=%s",
        symbol,
        interval,
        ema_fast_n,
        ema_slow_n,
        cfg.PAPER_TRADE,
    )

    contract_detail = client.get_contract_detail(symbol)
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
    current_pos = 0  # +1 long, -1 short, 0 flat

    while True:
        try:
            k = client.get_kline(symbol, interval=interval)
            if not (k and k.get("success") and "data" in k and "close" in k["data"]):
                logging.warning("Réponse klines inattendue: %s", k)
                time.sleep(cfg.LOOP_SLEEP_SECS)
                continue

            closes = k["data"]["close"][-cfg.MAX_KLINES:]
            if len(closes) < max(ema_fast_n, ema_slow_n) + 2:
                logging.info("Pas assez d’historique pour EMA; retry...")
                time.sleep(cfg.LOOP_SLEEP_SECS)
                continue

            efull = ema(closes, ema_fast_n)
            eslow = ema(closes, ema_slow_n)
            last_fast, prev_fast = efull[-1], efull[-2]
            last_slow, prev_slow = eslow[-1], eslow[-2]
            x = cross(last_fast, last_slow, prev_fast, prev_slow)

            tick = client.get_ticker(symbol)
            if not (tick and tick.get("success") and tick.get("data")):
                logging.warning("Ticker vide: %s", tick)
                time.sleep(cfg.LOOP_SLEEP_SECS)
                continue
            tdata = tick["data"]
            if isinstance(tdata, list):
                price: Optional[float] = None
                for row in tdata:
                    if row.get("symbol") == symbol:
                        price = float(row.get("lastPrice"))
                        break
                if price is None:
                    logging.warning("Prix introuvable pour %s", symbol)
                    time.sleep(cfg.LOOP_SLEEP_SECS)
                    continue
            else:
                price = float(tdata.get("lastPrice"))

            vol = compute_position_size(
                contract_detail,
                equity_usdt,
                price,
                cfg.RISK_PCT_EQUITY,
                cfg.LEVERAGE,
                symbol,
            )
            if vol <= 0:
                logging.info("vol calculé = 0; on attend.")
                time.sleep(cfg.LOOP_SLEEP_SECS)
                continue

            sl_long = price * (1.0 - cfg.STOP_LOSS_PCT)
            tp_long = price * (1.0 + cfg.TAKE_PROFIT_PCT)
            sl_short = price * (1.0 + cfg.STOP_LOSS_PCT)
            tp_short = price * (1.0 - cfg.TAKE_PROFIT_PCT)

            log_event(
                "signal",
                {
                    "fast": last_fast,
                    "slow": last_slow,
                    "cross": x,
                    "price": price,
                    "pos": current_pos,
                    "vol": vol,
                },
            )

            if x == +1 and current_pos <= 0:
                if current_pos < 0:
                    client.place_order(
                        symbol,
                        side=4,
                        vol=vol,
                        order_type=5,
                        price=price,
                        open_type=cfg.OPEN_TYPE,
                        leverage=cfg.LEVERAGE,
                        reduce_only=True,
                    )
                    current_pos = 0
                    time.sleep(0.3)
                resp = client.place_order(
                    symbol,
                    side=1,
                    vol=vol,
                    order_type=5,
                    price=price,
                    open_type=cfg.OPEN_TYPE,
                    leverage=cfg.LEVERAGE,
                    stop_loss=sl_long,
                    take_profit=tp_long,
                )
                log_event("order_long", resp)
                logging.info(
                    "→ LONG vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
                    vol,
                    price,
                    sl_long,
                    tp_long,
                    "paper" if cfg.PAPER_TRADE else "live",
                )
                current_pos = +1

            elif x == -1 and current_pos >= 0:
                if current_pos > 0:
                    client.place_order(
                        symbol,
                        side=2,
                        vol=vol,
                        order_type=5,
                        price=price,
                        open_type=cfg.OPEN_TYPE,
                        leverage=cfg.LEVERAGE,
                        reduce_only=True,
                    )
                    current_pos = 0
                    time.sleep(0.3)
                resp = client.place_order(
                    symbol,
                    side=3,
                    vol=vol,
                    order_type=5,
                    price=price,
                    open_type=cfg.OPEN_TYPE,
                    leverage=cfg.LEVERAGE,
                    stop_loss=sl_short,
                    take_profit=tp_short,
                )
                log_event("order_short", resp)
                logging.info(
                    "→ SHORT vol=%s @~%.2f (SL~%.2f / TP~%.2f) [%s]",
                    vol,
                    price,
                    sl_short,
                    tp_short,
                    "paper" if cfg.PAPER_TRADE else "live",
                )
                current_pos = -1

            time.sleep(cfg.LOOP_SLEEP_SECS)

        except KeyboardInterrupt:
            logging.info("Arrêt manuel.")
            break
        except Exception as e:  # pragma: no cover - runtime guard
            logging.exception("Erreur boucle principale: %s", str(e))
            time.sleep(3)


if __name__ == "__main__":
    main()
