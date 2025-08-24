#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot d'entrée unique : scan des signaux (par défaut) ou boucle orchestrée.
Compatible avec les packages 'scalp' et 'scalper' (import fallback).
"""

from __future__ import annotations
import os
import sys
import time
import argparse
from typing import Dict, List, Any, Optional

# --- Compat imports 'scalp' / 'scalper' --------------------------------------
def _import_strategy_factory():
    try:
        from scalp.strategy.factory import load_strategies_cfg, resolve_signal_fn
        return load_strategies_cfg, resolve_signal_fn
    except Exception:
        from scalper.strategy.factory import load_strategies_cfg, resolve_signal_fn
        return load_strategies_cfg, resolve_signal_fn

def _import_indicators_signal():
    try:
        from scalp.core.signal import Signal  # type: ignore
        return Signal
    except Exception:
        from scalper.core.signal import Signal  # type: ignore
        return Signal

def _import_orchestrator():
    try:
        from scalp.orchestrator import Orchestrator  # type: ignore
        return Orchestrator
    except Exception:
        from scalper.orchestrator import Orchestrator  # type: ignore
        return Orchestrator

def _import_exchange():
    """
    Retourne (BitgetExchange ou None, message d’aide).
    On tolère l’absence du client Bitget pour le mode 'scan --csv'.
    """
    candidates = [
        "scalp.exchanges.bitget",
        "scalper.exchanges.bitget",
    ]
    for mod_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=["BitgetExchange"])
            return getattr(mod, "BitgetExchange"), ""
        except Exception:
            continue
    return None, ("Client Bitget introuvable. Installe/active le module 'scalp.exchanges.bitget' "
                  "ou utilise le mode --csv pour scanner des signaux hors-ligne.")

# --- Transformateurs de données OHLCV ----------------------------------------
def _ohlcv_to_dict(rows: List[List[float]]) -> Dict[str, List[float]]:
    """
    rows: [[ts, open, high, low, close, volume], ...]
    -> dict de listes
    """
    cols = ("timestamp", "open", "high", "low", "close", "volume")
    out: Dict[str, List[float]] = {k: [] for k in cols}
    for r in rows:
        if len(r) < 6:
            raise ValueError("Ligne OHLCV invalide (6 colonnes attendues).")
        out["timestamp"].append(float(r[0]))
        out["open"].append(float(r[1]))
        out["high"].append(float(r[2]))
        out["low"].append(float(r[3]))
        out["close"].append(float(r[4]))
        out["volume"].append(float(r[5]))
    return out

def _read_csv(csv_path: str) -> Dict[str, List[float]]:
    import csv
    cols = ("timestamp", "open", "high", "low", "close", "volume")
    out = {k: [] for k in cols}
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            for k in cols:
                out[k].append(float(row[k]))
    return out

# --- Modes --------------------------------------------------------------------
def mode_scan(
    *,
    symbols: List[str],
    timeframe: str,
    cfg_path: str,
    csv: Optional[str],
    csv_1h: Optional[str],
    equity: float,
    risk: float,
) -> None:
    load_strategies_cfg, resolve_signal_fn = _import_strategy_factory()
    Signal = _import_indicators_signal()

    cfg = load_strategies_cfg(cfg_path)

    # Source des données : CSV (offline) ou Bitget (online)
    data_by_symbol: Dict[str, Dict[str, List[float]]] = {}
    data_1h_by_symbol: Dict[str, Dict[str, List[float]]] = {}

    if csv:
        # Un CSV pour tous (usage rapide) ; chacun peut pointer vers son propre CSV si besoin.
        data = _read_csv(csv)
        for s in symbols:
            data_by_symbol[s] = data
        if csv_1h:
            d1h = _read_csv(csv_1h)
            for s in symbols:
                data_1h_by_symbol[s] = d1h
    else:
        BitgetExchange, msg = _import_exchange()
        if BitgetExchange is None:
            print(msg)
            sys.exit(2)
        api_key = os.getenv("BITGET_API_KEY", "")
        api_secret = os.getenv("BITGET_API_SECRET", "")
        api_passphrase = os.getenv("BITGET_API_PASSPHRASE", "")
        client = BitgetExchange(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)

        for s in symbols:
            rows = client.get_ohlcv(symbol=s, timeframe=timeframe, limit=1500)  # -> [[ts,o,h,l,c,v],...]
            data_by_symbol[s] = _ohlcv_to_dict(rows)
            # 1h optionnel pour filtre MTF
            try:
                rows_1h = client.get_ohlcv(symbol=s, timeframe="1h", limit=1500)
                data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
            except Exception:
                pass

    # Scan et affichage
    for s in symbols:
        signal_fn = resolve_signal_fn(s, timeframe, cfg)
        ohlcv = data_by_symbol[s]
        ohlcv_1h = data_1h_by_symbol.get(s)
        sig = signal_fn(
            symbol=s, timeframe=timeframe, ohlcv=ohlcv, equity=equity, risk_pct=risk, ohlcv_1h=ohlcv_1h
        )
        print(f"\n=== {s} / {timeframe} ===")
        if sig is None:
            print("Aucun signal.")
        else:
            d = sig.as_dict()
            print(f"Signal: side={d['side']} entry={d['entry']:.6f} sl={d['sl']:.6f} "
                  f"tp1={d['tp1']:.6f} tp2={d['tp2']:.6f} score={d['score']} "
                  f"quality={d['quality']:.2f}")
            print("Reasons:", d.get("reasons", ""))

def mode_orchestrate(
    *,
    symbols: List[str],
    timeframe: str,
    cfg_path: str,
    interval_sec: int,
    equity: float,
    risk: float,
) -> None:
    Orchestrator = _import_orchestrator()
    load_strategies_cfg, resolve_signal_fn = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)

    BitgetExchange, msg = _import_exchange()
    if BitgetExchange is None:
        print(msg)
        sys.exit(2)

    api_key = os.getenv("BITGET_API_KEY", "")
    api_secret = os.getenv("BITGET_API_SECRET", "")
    api_passphrase = os.getenv("BITGET_API_PASSPHRASE", "")
    client = BitgetExchange(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)

    orch = Orchestrator(
        exchange_client=client,
        strategies_cfg=cfg,
        jobs=[(s, timeframe) for s in symbols],
        interval_sec=interval_sec,
        equity=equity,
        risk_pct=risk,
    )
    try:
        orch.loop()
    except KeyboardInterrupt:
        print("\nArrêt demandé (CTRL+C).")

# --- CLI ----------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bot d'entrée unique (scan / orchestrate)")
    ap.add_argument("--symbols", required=True, help="Ex: BTCUSDT,ETHUSDT")
    ap.add_argument("--tf", required=True, help="Ex: 5m, 15m, 1h")
    ap.add_argument("--cfg", default="scalper/config/strategies.yml", help="Fichier stratégies (YAML ou JSON)")
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--mode", choices=["scan", "orchestrate"], default="scan")
    ap.add_argument("--interval", type=int, default=60, help="Intervalle (s) pour orchestrate")
    ap.add_argument("--csv", default="", help="Chemin CSV OHLCV (optionnel pour scan offline)")
    ap.add_argument("--csv_1h", default="", help="Chemin CSV 1h (optionnel pour scan offline)")
    return ap.parse_args()

def main():
    args = parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        print("Aucun symbole.")
        sys.exit(2)

    if args.mode == "scan":
        mode_scan(
            symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
            csv=(args.csv or None), csv_1h=(args.csv_1h or None),
            equity=args.equity, risk=args.risk,
        )
    else:
        mode_orchestrate(
            symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
            interval_sec=args.interval, equity=args.equity, risk=args.risk,
        )

if __name__ == "__main__":
    main()