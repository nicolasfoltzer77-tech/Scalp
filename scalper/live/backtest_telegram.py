# scalper/live/backtest_telegram.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

from scalper.backtest.runner import run_multi, csv_loader_factory


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
        kv.get("symbols")
        or kv.get("s")
        or ",".join(defaults.get("top_symbols", []) or [])
    ).strip()
    tfs = (kv.get("tf") or kv.get("timeframes") or defaults.get("timeframe", "5m")).strip()
    data_dir = kv.get("data", "data")
    out_dir = kv.get("out", "result/backtests")
    cash = float(kv.get("cash", defaults.get("cash", 10_000)))
    risk = float(kv.get("risk", defaults.get("risk_pct", 0.005)))
    slip = float(kv.get("slippage_bps", defaults.get("slippage_bps", 2.0)))
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    tf_list = [t.strip() for t in tfs.split(",") if t.strip()]
    return BacktestArgs(
        symbols=sym_list,
        timeframes=tf_list,
        data_dir=data_dir,
        out_dir=out_dir,
        cash=cash,
        risk=risk,
        slippage_bps=slip,
    )


async def handle_backtest_command(
    *,
    notifier,
    cmd_tail: str,
    runtime_config: Dict[str, object],
) -> None:
    """
    Lance un backtest multi {symbols x timeframes} et envoie :
      - un récapitulatif texte (top 3 par perf),
      - le fichier summary.csv en pièce jointe Telegram (si possible).
    Exemple :
      /backtest symbols=BTCUSDT,ETHUSDT tf=1m,5m cash=12000 risk=0.005
    """
    args = parse_backtest_args(cmd_tail, runtime_config or {})
    if not args.symbols or not args.timeframes:
        await notifier.send(
            "⚠️ Usage: /backtest symbols=BTCUSDT,ETHUSDT tf=1m,5m [cash=10000 risk=0.005 slippage_bps=2]"
        )
        return

    await notifier.send(
        f"🧪 Backtest en cours…\n"
        f"• Symbols: {', '.join(args.symbols)}\n"
        f"• TF: {', '.join(args.timeframes)}\n"
        f"• Cash: {args.cash:.0f}  • Risk: {args.risk:.4f}  • Slippage: {args.slippage_bps} bps"
    )

    loader = csv_loader_factory(args.data_dir)
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(
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
    if summary_path.exists():
        df = pd.read_csv(summary_path)
        df = df.sort_values("return_pct", ascending=False)
        top = df.head(3)
        lines = ["✅ Backtest terminé. Top 3 (par %ret):"]
        for _, r in top.iterrows():
            lines.append(
                f"• {r['symbol']} {r['timeframe']} — ret {r['return_pct']:.2f}% "
                f"| trades {int(r['n_trades'])} | win {r['win_rate_pct']:.1f}% "
                f"| DD {r['max_dd_pct']:.1f}%"
            )
        await notifier.send("\n".join(lines))
        if hasattr(notifier, "send_document"):
            try:
                await notifier.send_document(summary_path, caption="📎 Résumé backtest")
            except Exception as e:
                await notifier.send(f"(info) Impossible d’envoyer summary.csv: {e}")
    else:
        await notifier.send("⚠️ Backtest terminé mais summary.csv introuvable.")