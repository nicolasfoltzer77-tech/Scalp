# scalper/live/backtest_telegram.py
from __future__ import annotations

import asyncio
import os
from typing import List

from scalper.backtest import BTCfg, run_multi
from scalper.services.utils import safe_call

# Exchange CCXT asynchrone pour OHLCV publics (Bitget)
async def _get_exchange():
    try:
        import ccxt.async_support as ccxt  # type: ignore
    except Exception:
        raise RuntimeError("CCXT n'est pas installé. Lance: pip install ccxt")
    return ccxt.bitget()

def _parse_symbols(defaults: List[str]) -> List[str]:
    env = os.getenv("BACKTEST_SYMBOLS", "")
    if env.strip():
        return [s.strip().upper() for s in env.split(",") if s.strip()]
    return defaults

async def handle_backtest_command(notifier, defaults: List[str], timeframe: str = "5m") -> None:
    """Lancé par l'orchestrateur quand l'utilisateur tape /backtest sur Telegram."""
    symbols = _parse_symbols(defaults)
    cash = float(os.getenv("BT_CASH", "10000"))
    risk = float(os.getenv("BT_RISK_PCT", "0.05"))
    slip = float(os.getenv("BT_SLIPPAGE_BPS", "0.0"))
    limit = int(os.getenv("BT_LIMIT", "1500"))

    await notifier.send(
        "🧪 Backtest en cours...\n"
        f"• Symbols: {', '.join(symbols)}\n"
        f"• TF: {timeframe}\n"
        f"• Cash: {cash:,.0f}  • Risk: {risk:0.4f}  • Slippage: {slip:0.1f} bps\n"
        f"• Source: exchange.fetch_ohlcv (adapté) + cache CSV"
    )

    async def _run():
        exchange = await _get_exchange()
        try:
            cfg = BTCfg(symbols=symbols, timeframe=timeframe, cash=cash,
                        risk_pct=risk, slippage_bps=slip, limit=limit)
            res = await run_multi(cfg, exchange)
            await notifier.send(f"✅ Backtest terminé. Résultats: `{res['out_dir']}`")
        finally:
            try:
                await exchange.close()
            except Exception:
                pass

    try:
        await safe_call(_run, label="backtest", max_retry=1)  # 1 tir = si fail on avertit
    except Exception as e:
        await notifier.send(f"⚠️ Backtest : erreur inattendue: {e}")