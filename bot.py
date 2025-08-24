#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Point d'entrée unique (scan/orchestrate) — agnostique de l'implémentation Exchange.
- Détecte automatiquement wrapper Bitget (get_ohlcv) ou ccxt (fetch_ohlcv).
- Normalise les symboles selon le client détecté (BTCUSDT <-> BTC/USDT[:USDT]).
- Charge .env si présent (python-dotenv facultatif).
"""

from __future__ import annotations
import os, sys, argparse, re
from typing import Dict, List, Any, Optional, Tuple

# ---- .env facultatif ---------------------------------------------------------
def _load_dotenv_if_any() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        here = os.getcwd()
        candidates = [os.path.join(here, ".env"), os.path.join(os.path.dirname(here), ".env")]
        for p in candidates:
            if os.path.isfile(p):
                load_dotenv(p)
                break
    except Exception:
        pass
_load_dotenv_if_any()

# ---- Factory stratégies ------------------------------------------------------
def _import_strategy_factory():
    from scalper.signals.factory import load_strategies_cfg, resolve_signal_fn
    return load_strategies_cfg, resolve_signal_fn

# ---- Orchestrator ------------------------------------------------------------
def _import_orchestrator():
    from scalper.live.orchestrator import Orchestrator
    return Orchestrator

# ---- Exchange loader (wrapper ou ccxt) ---------------------------------------
def _build_ccxt_bitget_from_env(default_type: str = "swap"):
    try:
        import ccxt  # type: ignore
    except Exception:
        return None
    api_key = os.getenv("BITGET_API_KEY", "")
    api_secret = os.getenv("BITGET_API_SECRET", "")
    api_passphrase = os.getenv("BITGET_API_PASSPHRASE", "")
    opts = {"options": {"defaultType": default_type}}
    if any([api_key, api_secret, api_passphrase]):
        return ccxt.bitget({"apiKey": api_key, "secret": api_secret, "password": api_passphrase, **opts})
    return ccxt.bitget(opts)  # public (lecture)

def _import_exchange() -> Tuple[Optional[Any], str, str]:
    """
    Retourne (ExchangeCtorOuClient, message_aide, mode)
    - mode = "wrapper" si classe BitgetExchange avec get_ohlcv
    - mode = "ccxt" si client ccxt.bitget (fetch_ohlcv)
    """
    candidates = [
        "scalper.exchanges.bitget",
        "scalper.exchange.bitget",
        "scalper.exchanges.bitget_ccxt",
        "scalper.exchange.bitget_ccxt",
    ]
    for mod_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=["BitgetExchange"])
            BitgetExchange = getattr(mod, "BitgetExchange", None)
            if BitgetExchange is not None:
                return BitgetExchange, "", "wrapper"
        except Exception:
            continue

    ccxt_client = _build_ccxt_bitget_from_env(default_type=os.getenv("BITGET_DEFAULT_TYPE", "swap"))
    if ccxt_client is not None:
        return ccxt_client, "", "ccxt"

    return None, ("Aucun exchange Bitget trouvé. Installe ton module wrapper "
                  "ou 'pip install ccxt' pour le fallback."), ""

# ---- Normalisation symboles --------------------------------------------------
_SPOT_QUOTES = ("USDT","USDC","BTC","ETH","EUR","USD","BUSD","DAI")

def _bitget_native_from_ccxt(sym: str) -> str:
    """ 'BTC/USDT:USDT' -> 'BTCUSDT' ; 'BTC/USDT' -> 'BTCUSDT' """
    if "/" in sym:
        base, quote_part = sym.split("/", 1)
        quote = quote_part.split(":")[0]  # 'USDT:USDT' -> 'USDT'
        return f"{base}{quote}".upper()
    return sym.replace(":", "").replace("-", "").upper()

def _ccxt_from_bitget_native(sym: str, default_type: str = "swap") -> str:
    """ 'BTCUSDT' -> 'BTC/USDT[:USDT]' selon default_type ('swap' -> ajouter :USDT). """
    s = sym.upper().replace("-", "").replace(":", "")
    # coupe en base/quote pour quotes connues
    for q in _SPOT_QUOTES:
        if s.endswith(q):
            base = s[:-len(q)]
            if default_type == "swap" and q in ("USDT","USDC"):
                return f"{base}/{q}:{q}"
            return f"{base}/{q}"
    # fallback (impossible à couper proprement)
    return sym

def _norm_symbol_for_client(sym: str, mode: str, default_type: str = "swap") -> str:
    if mode == "wrapper":    # ton exchange avec get_ohlcv → format Bitget natif
        return _bitget_native_from_ccxt(sym)
    elif mode == "ccxt":     # client ccxt → format ccxt
        return _ccxt_from_bitget_native(sym, default_type=default_type)
    return sym

# ---- Utils OHLCV offline -----------------------------------------------------
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

# ---- Modes -------------------------------------------------------------------
def mode_scan(
    *, symbols: List[str], timeframe: str, cfg_path: str,
    csv: Optional[str], csv_1h: Optional[str],
    equity: float, risk: float
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
        ExCtorOrClient, msg, mode = _import_exchange()
        if ExCtorOrClient is None:
            print(msg); return

        default_type = os.getenv("BITGET_DEFAULT_TYPE", "swap")

        if mode == "wrapper":
            # Classe BitgetExchange(...)
            client = ExCtorOrClient(
                api_key=os.getenv("BITGET_API_KEY",""),
                api_secret=os.getenv("BITGET_API_SECRET",""),
                api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
            )
            fetch = getattr(client, "get_ohlcv")
            for s in symbols:
                s_eff = _norm_symbol_for_client(s, mode="wrapper")
                rows = fetch(symbol=s_eff, timeframe=timeframe, limit=1500)
                data_by_symbol[s] = _ohlcv_to_dict(rows)
                try:
                    rows_1h = fetch(symbol=s_eff, timeframe="1h", limit=1500)
                    data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
                except Exception:
                    pass
        else:
            # ccxt client direct
            client = ExCtorOrClient
            for s in symbols:
                s_eff = _norm_symbol_for_client(s, mode="ccxt", default_type=default_type)
                rows = client.fetch_ohlcv(s_eff, timeframe=timeframe, limit=1500)
                data_by_symbol[s] = _ohlcv_to_dict(rows)
                try:
                    rows_1h = client.fetch_ohlcv(s_eff, timeframe="1h", limit=1500)
                    data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
                except Exception:
                    pass

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
    interval_sec: int, equity: float, risk: float
) -> None:
    Orchestrator = _import_orchestrator()
    load_strategies_cfg, _ = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)

    ExCtorOrClient, msg, mode = _import_exchange()
    if ExCtorOrClient is None:
        print(msg); return

    if mode == "wrapper":
        client = ExCtorOrClient(
            api_key=os.getenv("BITGET_API_KEY",""),
            api_secret=os.getenv("BITGET_API_SECRET",""),
            api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
        )
    else:
        client = ExCtorOrClient  # ccxt

    jobs = [(s, timeframe) for s in symbols]
    orch = Orchestrator(
        exchange_client=client, strategies_cfg=cfg, jobs=jobs,
        interval_sec=interval_sec, equity=equity, risk_pct=risk
    )
    try:
        orch.loop()
    except KeyboardInterrupt:
        print("\nArrêt demandé (CTRL+C).")

# ---- CLI ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bot (scan/orchestrate)")

    # Par défaut, on met un symbole neutre (format natif Bitget).
    default_symbols = os.getenv("DEFAULT_SYMBOLS", "BTCUSDT")
    default_tf = os.getenv("DEFAULT_TF", "5m")

    ap.add_argument("--symbols", default=default_symbols, help="Ex: BTCUSDT (wrapper) ou BTC/USDT:USDT (ccxt)")
    ap.add_argument("--tf", default=default_tf, help="Ex: 5m, 15m, 1h")
    ap.add_argument("--cfg", default="scalper/config/strategies.yml", help="Fichier stratégies (YAML/JSON)")
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--mode", choices=["scan","orchestrate"], default="scan")
    ap.add_argument("--interval", type=int, default=60, help="Intervalle (s) pour orchestrate")
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
            equity=args.equity, risk=args.risk
        )
    else:
        mode_orchestrate(
            symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
            interval_sec=args.interval, equity=args.equity, risk=args.risk
        )

if __name__ == "__main__":
    main()