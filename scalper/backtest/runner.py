# scalper/backtest/runner.py
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Callable

from .cache import ensure_csv_cache, read_csv_ohlcv, csv_path, tf_to_seconds, dump_validation_report

# --------- Chargement de la stratégie (factory commune si dispo) ---------
def load_signal_fn() -> Callable[[str, List[List[float]], float, float], Tuple[str, float]]:
    """
    Retourne une fonction (symbol, ohlcv, cash, risk_pct) -> (signal, strength[0..1])
    Utilise scalper.signals.factory si présent, sinon fallback simple (moyenne 10 closes).
    """
    try:
        from scalper.signals.factory import load_signal  # type: ignore
        name = os.getenv("STRATEGY", "current")
        return load_signal(name)
    except Exception:
        def _fallback(symbol: str, ohlcv: List[List[float]], cash: float, risk_pct: float) -> Tuple[str, float]:
            closes = [r[4] for r in (ohlcv[-10:] if len(ohlcv) >= 10 else ohlcv)]
            if not closes:
                return "HOLD", 0.0
            avg = sum(closes) / len(closes)
            last = closes[-1]
            if last > avg * 1.002:
                return "BUY", 1.0
            if last < avg * 0.998:
                return "SELL", 1.0
            return "HOLD", 0.0
        return _fallback

# --------- Config ---------

@dataclass
class BTCfg:
    symbols: List[str]
    timeframe: str = "5m"
    limit: int = 1500
    cash: float = 10_000.0
    risk_pct: float = 0.05
    slippage_bps: float = 0.0
    fee_bps: float = 6.0
    data_dir: str = "data"
    strategy: str = os.getenv("STRATEGY", "current")

# --------- Petit moteur de PnL (long/short, 1 position, all-in sur signal) ---------

def _bps(x: float) -> float:
    return x / 10_000.0

def simulate_symbol(ohlcv: List[List[float]], cfg: BTCfg, signal_fn: Callable) -> Tuple[List[Tuple[int,float]], Dict]:
    equity = cfg.cash
    position = 0.0  # quantité (peut être négative si short)
    entry_price = 0.0
    equity_curve: List[Tuple[int, float]] = []
    trades = 0

    fee = _bps(cfg.fee_bps)
    slip = _bps(cfg.slippage_bps)

    for i in range(1, len(ohlcv)):
        window = ohlcv[: i+1]  # historique jusqu'à la barre i incluse
        ts, _, _, _, price, _ = ohlcv[i]
        signal, strength = signal_fn("SYMBOL", window, equity, cfg.risk_pct)

        # mark-to-market
        if position != 0:
            equity += position * (price - ohlcv[i-1][4])

        # décisions sur changement de signal
        target_pos = 0.0
        if signal == "BUY":
            notional = equity * cfg.risk_pct * strength
            target_pos = max(0.0, notional / price)   # long
        elif signal == "SELL":
            notional = equity * cfg.risk_pct * strength
            target_pos = - max(0.0, notional / price) # short

        if target_pos != position:
            # frais & slippage sur la variation de position
            delta = target_pos - position
            if delta != 0:
                trades += 1
                trade_price = price * (1 + slip * (1 if delta > 0 else -1))
                equity -= abs(delta) * trade_price * fee
                # book au prix d’exécution (slippage)
                position = target_pos
                entry_price = trade_price if position != 0 else 0.0

        equity_curve.append((ts, equity))

    # fermeture forcée
    if position != 0 and ohlcv:
        last_price = ohlcv[-1][4]
        equity += position * (last_price - entry_price)
        equity -= abs(position) * last_price * fee
        position = 0

    # métriques très simples
    eq = [e for _, e in equity_curve]
    ret_tot = (eq[-1] / eq[0] - 1.0) if len(eq) >= 2 else 0.0
    max_dd = 0.0
    peak = -1.0
    for v in eq:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)

    # Sharpe annualisé grossier
    tf_sec = tf_to_seconds(cfg.timeframe)
    bars_per_year = int((365.0 * 86400.0) / tf_sec)
    rets = []
    for i in range(1, len(eq)):
        r = (eq[i] / eq[i-1]) - 1.0
        rets.append(r)
    if len(rets) > 1:
        mu = sum(rets) / len(rets)
        var = sum((x - mu) ** 2 for x in rets) / (len(rets) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        sharpe = (mu * bars_per_year) / (std * math.sqrt(bars_per_year)) if std > 0 else 0.0
    else:
        sharpe = 0.0

    metrics = {
        "final_equity": round(eq[-1], 4) if eq else cfg.cash,
        "total_return_pct": round(ret_tot * 100, 4),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "sharpe_like": round(sharpe, 4),
        "trades": trades,
    }
    return equity_curve, metrics

# --------- Runner principal ---------

async def run_multi(cfg: BTCfg, exchange) -> Dict:
    """
    - Valide/rafraîchit le cache CSV pour chaque symbole (selon fraîcheur TF)
    - Backteste la stratégie sur chaque symbole
    - Concatène les équités (moyenne simple) => equity_curve.csv
    - Sauve metrics.json
    """
    # 1) ensure cache
    data = await ensure_csv_cache(exchange, cfg.symbols, cfg.timeframe, cfg.limit)

    # 2) backtest par symbole
    signal_fn = load_signal_fn()
    per_symbol: Dict[str, Dict] = {}
    aligned_ts: List[int] = []

    # construire timeline commune (intersection)
    sets_ts = []
    for s in cfg.symbols:
        rows = data.get(s) or read_csv_ohlcv(csv_path(s, cfg.timeframe))
        sets_ts.append({r[0] for r in rows})
    if sets_ts:
        aligned_ts = sorted(list(set.intersection(*sets_ts)))

    # map ts->close pour performance
    results_curves: Dict[str, List[Tuple[int, float]]] = {}
    for s in cfg.symbols:
        rows = data.get(s) or read_csv_ohlcv(csv_path(s, cfg.timeframe))
        rows = [r for r in rows if r[0] in set(aligned_ts)]
        curve, metr = simulate_symbol(rows, cfg, signal_fn)
        results_curves[s] = curve
        per_symbol[s] = metr

    # 3) fusion des courbes (moyenne des équités)
    fused: List[Tuple[int, float]] = []
    for i in range(len(aligned_ts)):
        ts = aligned_ts[i]
        vals = []
        for s in cfg.symbols:
            cv = results_curves[s]
            if i < len(cv) and cv[i][0] == ts:
                vals.append(cv[i][1])
        if vals:
            fused.append((ts, sum(vals) / len(vals)))

    # 4) métriques globales (sur la courbe fusionnée)
    tmp_cfg = BTCfg(symbols=["AVG"], timeframe=cfg.timeframe, cash=cfg.cash, risk_pct=cfg.risk_pct,
                    slippage_bps=cfg.slippage_bps, fee_bps=cfg.fee_bps, limit=cfg.limit)
    glob_metrics = {}
    if fused:
        # réutilise calcul DD/Sharpe etc.
        eq = [e for _, e in fused]
        ret_tot = (eq[-1]/eq[0]-1.0) if len(eq)>=2 else 0.0
        # max DD
        peak = -1.0
        max_dd = 0.0
        for v in eq:
            if v > peak: peak = v
            dd = (peak - v) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        # sharpe-like
        tf_sec = tf_to_seconds(cfg.timeframe)
        bpy = int((365.0*86400.0)/tf_sec)
        rets = []
        for i in range(1, len(eq)):
            rets.append((eq[i]/eq[i-1]) - 1.0)
        if len(rets) > 1:
            mu = sum(rets)/len(rets)
            var = sum((x-mu)**2 for x in rets)/(len(rets)-1)
            std = math.sqrt(var) if var>0 else 0.0
            sharpe = (mu*bpy)/(std*math.sqrt(bpy)) if std>0 else 0.0
        else:
            sharpe = 0.0
        glob_metrics = {
            "final_equity": round(eq[-1], 4),
            "total_return_pct": round(ret_tot*100, 4),
            "max_drawdown_pct": round(max_dd*100, 4),
            "sharpe_like": round(sharpe, 4),
        }

    # 5) dump résultats
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_dir = Path(os.getenv("BACKTEST_OUT", f"result/backtest-{stamp}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # equity_curve.csv (courbe fusionnée)
    (out_dir / "equity_curve.csv").write_text(
        "timestamp,equity\n" + "\n".join(f"{ts},{eq:.6f}" for ts, eq in fused)
    )
    # metrics.json (global + détail par symbole)
    all_metrics = {"global": glob_metrics, "per_symbol": per_symbol}
    (out_dir / "metrics.json").write_text(json.dumps(all_metrics, indent=2))

    # rapport validation CSV
    dump_validation_report(cfg.symbols, cfg.timeframe, out_dir / "csv_validation.json")

    return {
        "out_dir": str(out_dir),
        "equity_curve": str(out_dir / "equity_curve.csv"),
        "metrics": str(out_dir / "metrics.json"),
        "csv_validation": str(out_dir / "csv_validation.json"),
    }

# --------- CLI facultative ---------

if __name__ == "__main__":
    import asyncio
    # Petit exchange CCXT Bitget (sans clés) uniquement pour fetch OHLCV publics
    try:
        import ccxt.async_support as ccxt  # type: ignore
    except Exception:
        raise SystemExit("Installe ccxt: pip install ccxt")

    symbols = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
    cfg = BTCfg(
        symbols=[s.strip().upper() for s in symbols if s.strip()],
        timeframe=os.getenv("TF", "5m"),
        limit=int(os.getenv("LIMIT", "1500")),
        cash=float(os.getenv("CASH", "10000")),
        risk_pct=float(os.getenv("RISK_PCT", "0.05")),
        slippage_bps=float(os.getenv("SLIPPAGE_BPS", "0.0")),
        fee_bps=float(os.getenv("FEE_BPS", "6.0")),
    )
    exchange = ccxt.bitget()
    res = asyncio.run(run_multi(cfg, exchange))
    print("Résultats écrits dans:", res["out_dir"])