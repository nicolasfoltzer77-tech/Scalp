#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Point d'entrée unique (scan/orchestrate) — agnostique de l'implémentation Exchange.
- Essaie d'abord tes modules 'scalper.exchanges.*' ou 'scalper.exchange.*'
- Sinon fallback ccxt (bitget) automatiquement si ccxt est installé.
- Charge .env si présent (python-dotenv facultatif).
"""

from __future__ import annotations
import os, sys, argparse
from typing import Dict, List, Any, Optional

# ---- .env facultatif ---------------------------------------------------------
def _load_dotenv_if_any() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        # cherche .env dans CWD puis parent (utile depuis notebooks/)
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
    # On a déplacé la factory sous scalper.signals.factory pour éviter le conflit 'scalper/strategy.py'
    from scalper.signals.factory import load_strategies_cfg, resolve_signal_fn
    return load_strategies_cfg, resolve_signal_fn

# ---- Orchestrator ------------------------------------------------------------
def _import_orchestrator():
    from scalper.live.orchestrator import Orchestrator
    return Orchestrator

# ---- Exchange loader (multi-essais + fallback ccxt) --------------------------
def _build_ccxt_bitget_from_env(default_type: str = "swap"):
    """
    Fallback ccxt: construit un client ccxt.bitget prêt à l'emploi (public ou privé).
    """
    try:
        import ccxt  # type: ignore
    except Exception:
        return None

    api_key = os.getenv("BITGET_API_KEY", "")
    api_secret = os.getenv("BITGET_API_SECRET", "")
    api_passphrase = os.getenv("BITGET_API_PASSPHRASE", "")

    opts = {"options": {"defaultType": default_type}}
    if any([api_key, api_secret, api_passphrase]):
        client = ccxt.bitget({"apiKey": api_key, "secret": api_secret, "password": api_passphrase, **opts})
    else:
        client = ccxt.bitget(opts)  # accès public (lecture OHLCV)

    # Pour compat DataFetcher (qui sait gérer fetch_ohlcv)
    return client

def _import_exchange() -> tuple[Optional[Any], str]:
    """
    Tente plusieurs chemins d'import pour ton exchange Bitget.
    Retourne (ExchangeCtor_ou_client, help_message)
    - Si on trouve une classe avec get_ohlcv(...), on la retourne (BitgetExchange).
    - Sinon on retourne un client ccxt prêt (ayant fetch_ohlcv).
    """
    candidates = [
        "scalper.exchanges.bitget",     # classique
        "scalper.exchange.bitget",      # autre convention
        "scalper.exchanges.bitget_ccxt",
        "scalper.exchange.bitget_ccxt",
    ]
    for mod_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=["BitgetExchange"])
            BitgetExchange = getattr(mod, "BitgetExchange", None)
            if BitgetExchange is not None:
                return BitgetExchange, ""
        except Exception:
            continue

    # Fallback ccxt (client déjà prêt)
    ccxt_client = _build_ccxt_bitget_from_env(default_type=os.getenv("BITGET_DEFAULT_TYPE", "swap"))
    if ccxt_client is not None:
        return ccxt_client, ""  # on renvoie directement l'instance ccxt

    # Rien trouvé
    return None, ("Aucun exchange Bitget trouvé. Installe/active ton module 'scalper.exchanges.bitget' "
                  "ou installe 'ccxt' pour le fallback (pip install ccxt).")

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
        ExchangeCtorOrClient, msg = _import_exchange()
        if ExchangeCtorOrClient is None:
            print(msg); return

        # Si c'est une classe wrapper -> instancie ; si c'est déjà un client ccxt -> utilise tel quel
        if hasattr(ExchangeCtorOrClient, "__call__") and ExchangeCtorOrClient.__name__ != "bitget":
            # Classe type BitgetExchange(...)
            client = ExchangeCtorOrClient(
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
            # ccxt client direct
            client = ExchangeCtorOrClient  # instance ccxt.bitget
            for s in symbols:
                rows = client.fetch_ohlcv(s, timeframe=timeframe, limit=1500)
                data_by_symbol[s] = _ohlcv_to_dict(rows)
                try:
                    rows_1h = client.fetch_ohlcv(s, timeframe="1h", limit=1500)
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

    ExchangeCtorOrClient, msg = _import_exchange()
    if ExchangeCtorOrClient is None:
        print(msg); return

    # Si classe -> instancier ; si ccxt client -> passer tel quel
    if hasattr(ExchangeCtorOrClient, "__call__") and ExchangeCtorOrClient.__name__ != "bitget":
        client = ExchangeCtorOrClient(
            api_key=os.getenv("BITGET_API_KEY",""),
            api_secret=os.getenv("BITGET_API_SECRET",""),
            api_passphrase=os.getenv("BITGET_API_PASSPHRASE",""),
        )
    else:
        client = ExchangeCtorOrClient  # instance ccxt

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

    default_symbols = os.getenv("DEFAULT_SYMBOLS", "BTC/USDT:USDT")  # ccxt symbol par défaut (swap)
    default_tf = os.getenv("DEFAULT_TF", "5m")

    ap.add_argument("--symbols", default=default_symbols, help="Ex: BTCUSDT ou BTC/USDT:USDT (ccxt)")
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