#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, argparse
from typing import Dict, List, Any, Optional

def _import_strategy_factory():
    from scalper.signals.factory import load_strategies_cfg, resolve_signal_fn
    return load_strategies_cfg, resolve_signal_fn

def _import_orchestrator():
    from scalper.live.orchestrator import Orchestrator
    return Orchestrator

def _import_exchange():
    try:
        from scalper.exchanges.bitget import BitgetExchange  # type: ignore
        return BitgetExchange, ""
    except Exception:
        msg = ("Client Bitget introuvable. Installe/active 'scalper.exchanges.bitget' "
               "ou utilise le mode --csv pour scanner des signaux hors-ligne.")
        return None, msg

def _ohlcv_to_dict(rows: List[List[float]]) -> Dict[str, List[float]]:
    cols = ("timestamp","open","high","low","close","volume")
    out = {k: [] for k in cols}
    for r in rows:
        if len(r) < 6:
            raise ValueError("Ligne OHLCV invalide (6 colonnes attendues).")
        out["timestamp"].append(float(r[0])); out["open"].append(float(r[1]))
        out["high"].append(float(r[2])); out["low"].append(float(r[3]))
        out["close"].append(float(r[4])); out["volume"].append(float(r[5]))
    return out

def _read_csv(path: str) -> Dict[str, List[float]]:
    import csv
    cols = ("timestamp","open","high","low","close","volume")
    out = {k: [] for k in cols}
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            for k in cols:
                out[k].append(float(row[k]))
    return out

def mode_scan(*, symbols: List[str], timeframe: str, cfg_path: str,
              csv: Optional[str], csv_1h: Optional[str],
              equity: float, risk: float) -> None:
    load_strategies_cfg, resolve_signal_fn = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)
    data_by_symbol: Dict[str, Dict[str, List[float]]] = {}
    data_1h_by_symbol: Dict[str, Dict[str, List[float]]] = {}

    if csv:
        data = _read_csv(csv)
        for s in symbols: data_by_symbol[s] = data
        if csv_1h:
            d1h = _read_csv(csv_1h)
            for s in symbols: data_1h_by_symbol[s] = d1h
    else:
        BitgetExchange, msg = _import_exchange()
        if BitgetExchange is None:
            print(msg); return
        client = BitgetExchange(
            api_key=os.getenv("BITGET_API_KEY",""),
            api_secret=os.getenv("BITGET_API_SECRET",""),
            api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
        )
        for s in symbols:
            rows = client.get_ohlcv(symbol=s, timeframe=timeframe, limit=1500)
            data_by_symbol[s] = _ohlcv_to_dict(rows)
            try:
                rows_1h = client.get_ohlcv(symbol=s, timeframe="1h", limit=1500)
                data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
            except Exception:
                pass

    for s in symbols:
        fn = resolve_signal_fn(s, timeframe, cfg)
        ohlcv = data_by_symbol.get(s)
        if not ohlcv:
            print(f"\n=== {s}/{timeframe} ===\nPas de données OHLCV.")
            continue
        sig = fn(symbol=s, timeframe=timeframe, ohlcv=ohlcv,
                 equity=equity, risk_pct=risk, ohlcv_1h=data_1h_by_symbol.get(s))
        print(f"\n=== {s} / {timeframe} ===")
        if sig is None:
            print("Aucun signal.")
        else:
            d = sig.as_dict()
            print(f"Signal: side={d['side']} entry={d['entry']:.6f} sl={d['sl']:.6f} "
                  f"tp1={d['tp1']:.6f} tp2={d['tp2']:.6f} score={d['score']} "
                  f"quality={d['quality']:.2f}")
            print("Reasons:", d.get("reasons",""))

def mode_orchestrate(*, symbols: List[str], timeframe: str, cfg_path: str,
                     interval_sec: int, equity: float, risk: float) -> None:
    Orchestrator = _import_orchestrator()
    load_strategies_cfg, _ = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)
    BitgetExchange, msg = _import_exchange()
    if BitgetExchange is None:
        print(msg); return
    client = BitgetExchange(
        api_key=os.getenv("BITGET_API_KEY",""),
        api_secret=os.getenv("BITGET_API_SECRET",""),
        api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
    )
    jobs = [(s, timeframe) for s in symbols]
    orch = Orchestrator(exchange_client=client, strategies_cfg=cfg, jobs=jobs,
                        interval_sec=interval_sec, equity=equity, risk_pct=risk)
    try:
        orch.loop()
    except KeyboardInterrupt:
        print("\nArrêt demandé (CTRL+C).")

def parse_args():
    ap = argparse.ArgumentParser(description="Bot (scan/orchestrate)")
    default_symbols = os.getenv("DEFAULT_SYMBOLS", "BTCUSDT")
    default_tf = os.getenv("DEFAULT_TF", "5m")
    ap.add_argument("--symbols", default=default_symbols, help="Ex: BTCUSDT,ETHUSDT")
    ap.add_argument("--tf", default=default_tf, help="Ex: 5m, 15m, 1h")
    ap.add_argument("--cfg", default="scalper/config/strategies.yml", help="Fichier stratégies (YAML/JSON)")
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--mode", choices=["scan","orchestrate"], default="scan")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--csv", default="")
    ap.add_argument("--csv_1h", default="")
    return ap.parse_args()

def main():
    args = parse_args()
    symbols = [s.strip().upper() for s in (args.symbols or "").split(",") if s.strip()]
    if not symbols:
        print("Aucun symbole (utilise --symbols ou DEFAULT_SYMBOLS)."); return
    if args.mode == "scan":
        mode_scan(symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
                  csv=(args.csv or None), csv_1h=(args.csv_1h or None),
                  equity=args.equity, risk=args.risk)
    else:
        mode_orchestrate(symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
                         interval_sec=args.interval, equity=args.equity, risk=args.risk)

if __name__ == "__main__":
    main()