# scalper/live/backtest_telegram.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

from scalper.backtest.runner import run_multi
from scalper.backtest.market_data import hybrid_loader_from_exchange
from scalper.adapters.bitget_fetch import ensure_bitget_fetch


@dataclass
class BacktestArgs:
    symbols: List[str]
    timeframes: List[str]
    data_dir: str = "data"
    out_dir: str = "result/backtests"
    cash: float = 10_000.0
    risk: float = 0.005
    slippage_bps: float = 2.0


def _parse_kv(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in text.strip().split():
        if "=" in p:
            k, v = p.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


def parse_backtest_args(cmd_tail: str, defaults: Dict[str, object]) -> BacktestArgs:
    kv = _parse_kv(cmd_tail)
    symbols = (
        kv.get("symbols") or kv.get("s") or ",".join(defaults.get("top_symbols", []) or []) or "BTCUSDT"
    ).strip()
    tfs = (kv.get("tf") or kv.get("timeframes") or defaults.get("timeframe", "5m")).strip()
    data_dir = kv.get("data", "data")
    out_dir = kv.get("out", "result/backtests")
    cash = float(kv.get("cash", defaults.get("cash", 10_000)))
    risk = float(kv.get("risk", defaults.get("risk_pct", 0.005)))
    risk = max(0.0, min(risk, 0.05))  # clamp sécurité
    slip = float(kv.get("slippage_bps", defaults.get("slippage_bps", 2.0)))
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    tf_list = [t.strip() for t in tfs.split(",") if t.strip()]
    return BacktestArgs(
        symbols=sym_list, timeframes=tf_list, data_dir=data_dir,
        out_dir=out_dir, cash=cash, risk=risk, slippage_bps=slip
    )


async def handle_backtest_command(
    *,
    notifier,
    cmd_tail: str,
    runtime_config: Dict[str, object],
    exchange=None,  # l'exchange live nous est passé par l'orchestrateur
) -> None:
    """
    Backtest multi {symbols x timeframes}:
      - utilise exchange.fetch_ohlcv (via adaptateur Bitget au besoin)
      - met en cache CSV dans data/
      - envoie summary.csv + résumé texte
    """
    try:
        args = parse_backtest_args(cmd_tail, runtime_config or {})
        if not args.symbols or not args.timeframes:
            await notifier.send(
                "⚠️ Usage: /backtest symbols=BTCUSDT,ETHUSDT tf=1m,5m "
                "[cash=10000 risk=0.005 slippage_bps=2 data=data out=result/backtests]"
            )
            return

        # Assure que l'exchange dispose d'un fetch_ohlcv CCXT-like
        ex = ensure_bitget_fetch(exchange, market_hint=None)

        await notifier.send(
            "🧪 Backtest en cours…\n"
            f"• Symbols: {', '.join(args.symbols)}\n"
            f"• TF: {', '.join(args.timeframes)}\n"
            f"• Cash: {args.cash:.0f}  • Risk: {args.risk:.4f}  • Slippage: {args.slippage_bps} bps\n"
            "• Source: exchange.fetch_ohlcv (adapté) + cache CSV"
        )

        loader = hybrid_loader_from_exchange(ex, data_dir=args.data_dir, api_limit=1000)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: run_multi(
                symbols=args.symbols,
                timeframes=args.timeframes,
                loader=loader,
                out_dir=args.out_dir,
                initial_cash=args.cash,
                risk_pct=args.risk,
                slippage_bps=args.slippage_bps,
            ),
        )

        summary_path = Path(args.out_dir) / "summary.csv"
        if not summary_path.exists():
            await notifier.send("⚠️ Backtest terminé mais summary.csv introuvable.")
            return

        df = pd.read_csv(summary_path).sort_values("return_pct", ascending=False)
        lines = ["✅ Backtest terminé. Top 3 (par %ret):"]
        for _, r in df.head(3).iterrows():
            lines.append(
                f"• {r['symbol']} {r['timeframe']} — ret {r['return_pct']:.2f}% "
                f"| trades {int(r['n_trades'])} | win {r['win_rate_pct']:.1f}% | DD {r['max_dd_pct']:.1f}%"
            )
        await notifier.send("\n".join(lines))
        if hasattr(notifier, "send_document"):
            try:
                await notifier.send_document(summary_path, caption="📎 Résumé backtest")
            except Exception as e:
                await notifier.send(f"(info) Envoi summary.csv impossible: {e}")

    except Exception as e:
        await notifier.send(f"⚠️ Backtest : erreur inattendue: {e}")