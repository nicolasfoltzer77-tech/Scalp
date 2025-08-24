#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Point d'entrée unique (scan/orchestrate).

Principe:
- --exchange wrapper (défaut) : *pass-through* complet vers TON wrapper Bitget.
  -> on ne touche NI au symbole, NI au timeframe. C'est le wrapper qui gère.
- --exchange ccxt : utilise ccxt.bitget (pour debug rapide).
- --csv / --csv_1h : scan offline.

Exemples:
  python bot.py --symbols BTCUSDT --tf 5m                     # wrapper pass-through
  python bot.py --symbols BTCUSDT --tf 5m --exchange ccxt     # ccxt (transforme en BTC/USDT:USDT)
  python bot.py --csv data/BTCUSDT-5m.csv --csv_1h data/BTCUSDT-1h.csv
"""

from __future__ import annotations
import os, sys, argparse
from typing import Dict, List, Any, Optional, Tuple

# ---------- .env (facultatif) ----------
def _load_dotenv_if_any() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        here = os.getcwd()
        for p in (os.path.join(here, ".env"), os.path.join(os.path.dirname(here), ".env")):
            if os.path.isfile(p):
                load_dotenv(p)
                break
    except Exception:
        pass
_load_dotenv_if_any()

# ---------- Strategies ----------
def _import_strategy_factory():
    from scalper.signals.factory import load_strategies_cfg, resolve_signal_fn
    return load_strategies_cfg, resolve_signal_fn

# ---------- Orchestrator ----------
def _import_orchestrator():
    from scalper.live.orchestrator import Orchestrator
    return Orchestrator

# ---------- Exchange loader ----------
def _import_wrapper_class() -> Optional[Any]:
    for mod_name in (
        "scalper.exchange.bitget",
        "scalper.exchanges.bitget",
        "scalper/exchange/bitget",   # au cas où
    ):
        try:
            mod = __import__(mod_name, fromlist=["BitgetExchange"])
            cls = getattr(mod, "BitgetExchange", None)
            if cls is not None:
                return cls
        except Exception:
            continue
    return None

def _build_ccxt_bitget():
    try:
        import ccxt  # type: ignore
    except Exception:
        return None
    k = os.getenv("BITGET_API_KEY","")
    s = os.getenv("BITGET_API_SECRET","")
    p = os.getenv("BITGET_API_PASSPHRASE","")
    default_type = os.getenv("BITGET_DEFAULT_TYPE","swap")
    opts = {"options": {"defaultType": default_type}}
    if any([k,s,p]):
        return ccxt.bitget({"apiKey": k, "secret": s, "password": p, **opts})
    return ccxt.bitget(opts)

def _resolve_exchange(mode: str) -> Tuple[Optional[Any], str, str]:
    """Retourne (ExchangeCtorOrClient, message, detected_mode['wrapper'|'ccxt'])."""
    if mode == "wrapper":
        cls = _import_wrapper_class()
        if cls is None:
            return None, "Wrapper Bitget introuvable (scalper.exchange.bitget).", ""
        return cls, "", "wrapper"
    if mode == "ccxt":
        client = _build_ccxt_bitget()
        if client is None:
            return None, "ccxt non installé (pip install ccxt).", ""
        return client, "", "ccxt"
    # auto
    cls = _import_wrapper_class()
    if cls is not None:
        return cls, "", "wrapper"
    client = _build_ccxt_bitget()
    if client is not None:
        return client, "", "ccxt"
    return None, "Aucun exchange Bitget trouvé (wrapper ou ccxt).", ""

# ---------- Utils OHLCV offline ----------
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

# ---------- Modes ----------
def mode_scan(
    *, symbols: List[str], timeframe: str, cfg_path: str,
    csv: Optional[str], csv_1h: Optional[str],
    equity: float, risk: float, exchange_mode: str
) -> None:
    load_strategies_cfg, resolve_signal_fn = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)

    data_by_symbol: Dict[str, Dict[str, List[float]]] = {}
    data_1h_by_symbol: Dict[str, Dict[str, List[float]]] = {}

    if csv:
        data = _read_csv(csv)
        for s in symbols:
            data_by_symbol[s] = data
        if csv_1h:
            d1h = _read_csv(csv_1h)
            for s in symbols:
                data_1h_by_symbol[s] = d1h
    else:
        ExCtorOrClient, msg, detected = _resolve_exchange(exchange_mode)
        if ExCtorOrClient is None:
            print(msg); return

        if detected == "wrapper":
            # ⬇️ PASS-THROUGH : on n’ajoute ni suffixe, ni conversion.
            client = ExCtorOrClient(
                api_key=os.getenv("BITGET_API_KEY",""),
                api_secret=os.getenv("BITGET_API_SECRET",""),
                api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
            )
            fetch = getattr(client, "get_ohlcv")
            for s in symbols:
                rows = fetch(symbol=s, timeframe=timeframe, limit=1500)
                data_by_symbol[s] = _ohlcv_to_dict(rows)
                try:
                    rows_1h = fetch(symbol=s, timeframe="1h", limit=1500)
                    data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
                except Exception:
                    pass
        else:
            # ccxt : on convertit *au besoin* en BTC/USDT:USDT si l'utilisateur a mis BTCUSDT
            client = ExCtorOrClient
            default_type = os.getenv("BITGET_DEFAULT_TYPE","swap")
            def _to_ccxt(sym: str) -> str:
                if "/" in sym:
                    return sym
                # BTCUSDT -> BTC/USDT[:USDT]
                base, quote = sym[:-4], sym[-4:]
                if default_type == "swap":
                    return f"{base}/{quote}:{quote}"
                return f"{base}/{quote}"
            for s in symbols:
                s_eff = _to_ccxt(s)
                rows = client.fetch_ohlcv(s_eff, timeframe=timeframe, limit=1500)
                data_by_symbol[s] = _ohlcv_to_dict(rows)
                try:
                    rows_1h = client.fetch_ohlcv(s_eff, timeframe="1h", limit=1500)
                    data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
                except Exception:
                    pass

    # ---- Génération de signal
    for s in symbols:
        fn = resolve_signal_fn(s, timeframe, cfg)
        ohlcv = data_by_symbol.get(s)
        print(f"\n=== {s} / {timeframe} ===")
        if not ohlcv:
            print("Pas de données OHLCV."); continue
        sig = fn(symbol=s, timeframe=timeframe, ohlcv=ohlcv,
                 equity=equity, risk_pct=risk, ohlcv_1h=data_1h_by_symbol.get(s))
        if sig is None:
            print("Aucun signal.")
        else:
            d = sig.as_dict()
            print(f"Signal: side={d['side']} entry={d['entry']:.6f} sl={d['sl']:.6f} "
                  f"tp1={d['tp1']:.6f} tp2={d['tp2']:.6f} score={d['score']} "
                  f"quality={d['quality']:.2f}")
            print("Reasons:", d.get("reasons",""))

def mode_orchestrate(
    *, symbols: List[str], timeframe: str, cfg_path: str,
    interval_sec: int, equity: float, risk: float, exchange_mode: str
) -> None:
    Orchestrator = _import_orchestrator()
    load_strategies_cfg, _ = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)

    ExCtorOrClient, msg, detected = _resolve_exchange(exchange_mode)
    if ExCtorOrClient is None:
        print(msg); return

    if detected == "wrapper":
        client = ExCtorOrClient(
            api_key=os.getenv("BITGET_API_KEY",""),
            api_secret=os.getenv("BITGET_API_SECRET",""),
            api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
        )
    else:
        client = ExCtorOrClient  # ccxt client

    jobs = [(s, timeframe) for s in symbols]
    orch = Orchestrator(
        exchange_client=client, strategies_cfg=cfg, jobs=jobs,
        interval_sec=interval_sec, equity=equity, risk_pct=risk
    )
    try:
        orch.loop()
    except KeyboardInterrupt:
        print("\nArrêt demandé (CTRL+C).")

# ---------- CLI ----------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bot (scan/orchestrate)")
    ap.add_argument("--symbols", default=os.getenv("DEFAULT_SYMBOLS","BTCUSDT"),
                    help="Ex: BTCUSDT (wrapper) ou BTC/USDT:USDT (ccxt). Liste séparée par virgules.")
    ap.add_argument("--tf", default=os.getenv("DEFAULT_TF","5m"), help="Ex: 1m, 5m, 15m, 1h")
    ap.add_argument("--cfg", default="scalper/config/strategies.yml", help="Fichier stratégies (YAML/JSON)")
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--mode", choices=["scan","orchestrate"], default="scan")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--exchange", choices=["auto","wrapper","ccxt"], default=os.getenv("EXCHANGE_MODE","wrapper"),
                    help="wrapper = ton module (pass-through) ; ccxt = client ccxt.")
    ap.add_argument("--csv", default="", help="CSV OHLCV principal (scan offline)")
    ap.add_argument("--csv_1h", default="", help="CSV 1h (scan offline)")
    return ap.parse_args()

def main():
    args = parse_args()
    symbols = [s.strip() for s in (args.symbols or "").split(",") if s.strip()]
    if not symbols:
        print("Aucun symbole fourni (utilise --symbols ou DEFAULT_SYMBOLS).")
        return

    if args.mode == "scan":
        mode_scan(
            symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
            csv=(args.csv or None), csv_1h=(args.csv_1h or None),
            equity=args.equity, risk=args.risk, exchange_mode=args.exchange
        )
    else:
        mode_orchestrate(
            symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
            interval_sec=args.interval, equity=args.equity, risk=args.risk,
            exchange_mode=args.exchange
        )

if __name__ == "__main__":
    main()