#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Point d'entrée unique (scan/orchestrate), agnostique exchange.
- --exchange auto|wrapper|ccxt  (auto = détection)
- --market spot|umcbl           (pour wrapper Bitget: suffixe _SPBL / _UMCBL)
- Normalise les symboles automatiquement selon le mode.
"""

from __future__ import annotations
import os, sys, argparse
from typing import Dict, List, Any, Optional, Tuple

# ---------- .env facultatif ----------
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

# ---------- Strategies factory ----------
def _import_strategy_factory():
    from scalper.signals.factory import load_strategies_cfg, resolve_signal_fn
    return load_strategies_cfg, resolve_signal_fn

# ---------- Orchestrator ----------
def _import_orchestrator():
    from scalper.live.orchestrator import Orchestrator
    return Orchestrator

# ---------- Exchange loader ----------
def _build_ccxt_bitget_from_env(default_type: str = "swap"):
    try:
        import ccxt  # type: ignore
    except Exception:
        return None
    opts = {"options": {"defaultType": default_type}}
    k, s, p = os.getenv("BITGET_API_KEY",""), os.getenv("BITGET_API_SECRET",""), os.getenv("BITGET_API_PASSPHRASE","")
    if any([k, s, p]):
        return ccxt.bitget({"apiKey": k, "secret": s, "password": p, **opts})
    return ccxt.bitget(opts)

def _import_wrapper_class() -> Optional[Any]:
    for mod_name in (
        "scalper.exchanges.bitget",
        "scalper.exchange.bitget",
        "scalper.exchanges.bitget_ccxt",
        "scalper.exchange.bitget_ccxt",
    ):
        try:
            mod = __import__(mod_name, fromlist=["BitgetExchange"])
            cls = getattr(mod, "BitgetExchange", None)
            if cls is not None:
                return cls
        except Exception:
            continue
    return None

def _resolve_exchange(mode: str, default_type: str) -> Tuple[Optional[Any], str, str]:
    """
    Retourne (ExchangeCtorOuClient, message, detected_mode['wrapper'|'ccxt']).
    """
    if mode == "wrapper":
        cls = _import_wrapper_class()
        if cls is None:
            return None, "Module wrapper Bitget introuvable.", ""
        return cls, "", "wrapper"

    if mode == "ccxt":
        client = _build_ccxt_bitget_from_env(default_type=default_type)
        if client is None:
            return None, "ccxt non installé (pip install ccxt).", ""
        return client, "", "ccxt"

    # auto
    cls = _import_wrapper_class()
    if cls is not None:
        return cls, "", "wrapper"
    client = _build_ccxt_bitget_from_env(default_type=default_type)
    if client is not None:
        return client, "", "ccxt"
    return None, "Aucun exchange Bitget trouvé (wrapper ou ccxt).", ""

# ---------- Normalisation symboles ----------
_SPOT_SUFFIX = "_SPBL"
_SWAP_USDT_SUFFIX = "_UMCBL"  # perp USDT
_SPOT_QUOTES = ("USDT","USDC","BTC","ETH","EUR","USD","BUSD","DAI")

def _bitget_native_from_generic(sym: str, market: str) -> str:
    """
    'BTCUSDT' ou 'BTC/USDT:USDT' -> 'BTCUSDT_SPBL' (spot) ou 'BTCUSDT_UMCBL' (umcbl).
    """
    # 1) base/quote
    if "/" in sym:
        base, rest = sym.split("/", 1)
        quote = rest.split(":")[0]
        core = f"{base}{quote}".upper()
    else:
        core = sym.replace("-", "").replace(":", "").upper()
    # 2) suffix selon marché
    if market == "spot":
        return core + _SPOT_SUFFIX
    return core + _SWAP_USDT_SUFFIX  # défaut: perp USDT

def _ccxt_from_generic(sym: str, default_type: str = "swap") -> str:
    """
    'BTCUSDT' -> 'BTC/USDT:USDT' (swap) ou 'BTC/USDT' (spot).
    """
    s = sym.upper().replace("-", "").replace(":", "")
    # essaie de couper base/quote
    for q in _SPOT_QUOTES:
        if s.endswith(q):
            base = s[:-len(q)]
            if default_type == "swap" and q in ("USDT","USDC"):
                return f"{base}/{q}:{q}"
            return f"{base}/{q}"
    # si l'utilisateur a déjà donné le format ccxt, garde-le
    if "/" in sym:
        return sym
    return sym  # fallback

def _norm_symbol(sym: str, mode: str, market: str, default_type: str) -> str:
    if mode == "wrapper":
        return _bitget_native_from_generic(sym, market)
    if mode == "ccxt":
        return _ccxt_from_generic(sym, default_type=default_type)
    return sym

# ---------- Utils offline ----------
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

# ---------- Modes ----------
def mode_scan(
    *, symbols: List[str], timeframe: str, cfg_path: str,
    csv: Optional[str], csv_1h: Optional[str],
    equity: float, risk: float, exchange_mode: str, market: str, default_type: str
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
        ExCtorOrClient, msg, detected = _resolve_exchange(exchange_mode, default_type)
        if ExCtorOrClient is None:
            print(msg); return

        if detected == "wrapper":
            client = ExCtorOrClient(
                api_key=os.getenv("BITGET_API_KEY",""),
                api_secret=os.getenv("BITGET_API_SECRET",""),
                api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
            )
            fetch = getattr(client, "get_ohlcv")
            for s in symbols:
                s_eff = _norm_symbol(s, mode="wrapper", market=market, default_type=default_type)
                rows = fetch(symbol=s_eff, timeframe=timeframe, limit=1500)
                data_by_symbol[s] = _ohlcv_to_dict(rows)
                try:
                    rows_1h = fetch(symbol=_bitget_native_from_generic(s, market="umcbl"), timeframe="1h", limit=1500)
                    data_1h_by_symbol[s] = _ohlcv_to_dict(rows_1h)
                except Exception:
                    pass
        else:
            client = ExCtorOrClient  # ccxt
            for s in symbols:
                s_eff = _norm_symbol(s, mode="ccxt", market=market, default_type=default_type)
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
    interval_sec: int, equity: float, risk: float,
    exchange_mode: str, market: str, default_type: str
) -> None:
    Orchestrator = _import_orchestrator()
    load_strategies_cfg, _ = _import_strategy_factory()
    cfg = load_strategies_cfg(cfg_path)

    ExCtorOrClient, msg, detected = _resolve_exchange(exchange_mode, default_type)
    if ExCtorOrClient is None:
        print(msg); return

    if detected == "wrapper":
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

# ---------- CLI ----------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bot (scan/orchestrate)")

    ap.add_argument("--symbols", default=os.getenv("DEFAULT_SYMBOLS", "BTCUSDT"),
                    help="Ex: BTCUSDT (wrapper) ou BTC/USDT:USDT (ccxt). Liste séparée par des virgules.")
    ap.add_argument("--tf", default=os.getenv("DEFAULT_TF", "5m"), help="Ex: 1m, 5m, 15m, 1h")
    ap.add_argument("--cfg", default="scalper/config/strategies.yml", help="Fichier stratégies (YAML/JSON)")
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--mode", choices=["scan","orchestrate"], default="scan")
    ap.add_argument("--interval", type=int, default=60, help="Intervalle (s) pour orchestrate")

    # Nouveaux:
    ap.add_argument("--exchange", choices=["auto","wrapper","ccxt"],
                    default=os.getenv("EXCHANGE_MODE", "auto"),
                    help="Forcer l'exchange: 'wrapper' (ton module), 'ccxt', ou 'auto'.")
    ap.add_argument("--market", choices=["spot","umcbl"],
                    default=os.getenv("BITGET_MARKET","umcbl"),
                    help="Pour le wrapper: 'spot' -> _SPBL, 'umcbl' -> _UMCBL.")
    ap.add_argument("--default_type", choices=["spot","swap"],
                    default=os.getenv("BITGET_DEFAULT_TYPE","swap"),
                    help="Pour ccxt: defaultType (lecture OHLCV).")

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
            equity=args.equity, risk=args.risk,
            exchange_mode=args.exchange, market=args.market, default_type=args.default_type
        )
    else:
        mode_orchestrate(
            symbols=symbols, timeframe=args.tf, cfg_path=args.cfg,
            interval_sec=args.interval, equity=args.equity, risk=args.risk,
            exchange_mode=args.exchange, market=args.market, default_type=args.default_type
        )

if __name__ == "__main__":
    main()