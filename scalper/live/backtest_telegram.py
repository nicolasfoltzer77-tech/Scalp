# scalper/live/backtest_telegram.py
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional, Dict

from scalper.backtest.runner import BTConfig, run_single, run_multi, save_results

# ------------------------------------------------------------
# Parsing simple: /backtest symbols=BTCUSDT,ETHUSDT tf=5m cash=10000 risk=0.005 fees=6 slip=0 start= end=
# Si symbols absent -> on prend la watchlist/les paires de l’orchestrateur
# ------------------------------------------------------------

def _parse_backtest_args(text: str) -> Dict[str, str]:
    # text: "/backtest ..." -> dict params
    parts = text.strip().split()
    out: Dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out

DEFAULT_TOP = [
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT",
    "DOGEUSDT","ADAUSDT","LTCUSDT","AVAXUSDT","LINKUSDT",
]

def _extract_symbols(args: Dict[str, str], orch) -> List[str]:
    if "symbols" in args and args["symbols"]:
        return [s.strip().upper() for s in args["symbols"].split(",") if s.strip()]
    # sinon on tente l’orchestrateur
    if hasattr(orch, "symbols") and orch.symbols:
        return list(orch.symbols)
    if hasattr(orch, "watchlist") and getattr(orch.watchlist, "current", None):
        return list(getattr(orch.watchlist, "current"))
    return DEFAULT_TOP

def _as_float(args: Dict[str,str], key: str, default: float) -> float:
    try:
        return float(args.get(key, default))
    except Exception:
        return float(default)

def _as_int(args: Dict[str,str], key: str, default: int) -> int:
    try:
        return int(args.get(key, default))
    except Exception:
        return int(default)

# ------------------------------------------------------------
# Handler principal
# ------------------------------------------------------------

async def handle_backtest_command(text: str, orch, notifier) -> None:
    """
    Lance un backtest en tâche async.
    - orch: instance Orchestrator (pour récupérer les paires si non précisées)
    - notifier: Notifier (send)
    """
    args = _parse_backtest_args(text)

    symbols   = _extract_symbols(args, orch)
    timeframe = args.get("tf", args.get("timeframe", "5m")).lower()
    cash      = _as_float(args, "cash", 10_000.0)
    risk      = _as_float(args, "risk", 0.005)            # 0.5% par défaut
    fees_bps  = _as_float(args, "fees", _as_float(args, "fees_bps", 6.0))
    slip_bps  = _as_float(args, "slip", _as_float(args, "slip_bps", 0.0))
    limit     = _as_int(args, "limit", 1000)
    data_dir  = args.get("data_dir", os.getenv("DATA_DIR", "data"))
    out_dir   = args.get("out_dir", "result/backtests")
    strategy  = args.get("strategy", "current")
    start     = args.get("start", None)
    end       = args.get("end", None)

    # message de lancement
    await notifier.send(
        "🧪 Backtest en cours...\n"
        f"• Symbols: {', '.join(symbols)}\n"
        f"• TF: {timeframe}\n"
        f"• Cash: {cash:,.0f}  • Risk: {risk:0.4f}  • Slippage: {slip_bps:0.1f} bps\n"
        f"• Frais: {fees_bps:0.1f} bps  • Source: CSV+CCXT (cache auto)\n"
    )

    cfg = BTConfig(
        timeframe=timeframe, cash=cash, risk_pct=risk,
        fees_bps=fees_bps, slippage_bps=slip_bps, limit=limit,
        data_dir=data_dir, out_dir=out_dir, strategy_name=strategy,
        start=start, end=end,
    )

    async def _run():
        try:
            # exécution (mono/multi)
            if len(symbols) == 1:
                res = run_single(symbols[0], cfg)
            else:
                res = run_multi(symbols, cfg)

            tag = f"{timeframe}-{strategy}-{len(symbols)}sym"
            out_path = save_results(tag, res, cfg.out_dir)

            await notifier.send(
                "✅ Backtest terminé.\n"
                f"• Résultats: `{out_path}`\n"
                f"• equity_curve.csv / trades.csv / metrics.json"
            )
        except Exception as e:
            await notifier.send(f"⚠️ Backtest : erreur inattendue: `{e}`")

    # tâche de fond
    asyncio.create_task(_run())
    await notifier.send("🧪 Backtest lancé en tâche de fond.")