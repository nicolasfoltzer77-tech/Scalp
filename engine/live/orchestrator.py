# engine/live/orchestrator.py
from __future__ import annotations

import asyncio
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from engine.config.loader import load_config
from engine.config.strategies import load_strategies
from engine.config.watchlist import load_watchlist
from engine.backtest.loader_csv import load_csv_ohlcv  # lecture OHLCV

# ============================================================
# Config & Modèle
# ============================================================

@dataclass
class RunConfig:
    symbols: List[str]       # univers (watchlist)
    tfs: List[str]           # plusieurs TF à gérer en colonnes
    refresh_secs: int        # cadence d’affichage/évaluation
    data_dir: str            # data_dir (csv)
    limit: int               # nb de bougies lors backfill
    auto: bool = True        # déclencher refresh/backtest/promote automatiquement

_TF_MIN = {"1m":1, "5m":5, "15m":15, "1h":60, "4h":240, "1d":1440}

def _tf_minutes(tf: str) -> int:
    return _TF_MIN.get(str(tf), 1)

# seuil fraîcheur (1×TF -> ROUGE rapide)
def _is_fresh(now_ms: int, last_ms: Optional[int], tf: str) -> bool:
    if last_ms is None: return False
    return (now_ms - last_ms) <= (_tf_minutes(tf) * 60_000)

# ============================================================
# OHLCV & Stratégies
# ============================================================

def _last_ts_ms(data_dir: str, symbol: str, tf: str) -> Optional[int]:
    try:
        rows = load_csv_ohlcv(data_dir, symbol, tf, max_rows=1)
        return int(rows[-1][0]) if rows else None
    except Exception:
        return None

def _strat_valid(strats: Dict[str, Dict], symbol: str, tf: str) -> bool:
    s = strats.get(f"{symbol}:{tf}")
    return bool(s) and not bool(s.get("expired"))

# ============================================================
# Statut / Couleurs
# ============================================================

_COL = {"k":"\x1b[30m","r":"\x1b[31m","g":"\x1b[32m","o":"\x1b[33m","x":"\x1b[0m"}

def _short(s: str) -> str:
    s = s.upper().replace("_","")
    return s[:-4] if s.endswith("USDT") else s

def _status_cell(data_dir: str, strats: Dict[str, Dict], symbol: str, tf: str) -> Tuple[str,str]:
    now = int(time.time()*1000)
    last = _last_ts_ms(data_dir, symbol, tf)
    if last is None:              return ("MIS","k")  # noir
    if not _is_fresh(now, last, tf): return ("OLD","r")  # rouge
    if _strat_valid(strats, symbol, tf): return ("OK ","g")  # vert
    return ("DAT","o")  # orange

# ============================================================
# Rendu tableau multi‑TF (centré)
# ============================================================

def _center(t: str, w: int) -> str:
    pad = max(0, w-len(t)); return " "*(pad//2)+t+" "*(pad-pad//2)

def _render(symbols: List[str], tfs: List[str], data_dir: str, strats: Dict[str,Dict]) -> Tuple[str, Dict[Tuple[str,str], Tuple[str,str]]]:
    header = ["PAIR", *tfs]
    rows: List[List[str]] = []
    states: Dict[Tuple[str,str], Tuple[str,str]] = {}

    for s in symbols:
        one = [_short(s)]
        for tf in tfs:
            lbl, c = _status_cell(data_dir, strats, s, tf)
            states[(s,tf)] = (lbl,c)
            one.append(f"{_COL[c]}{lbl}{_COL['x']}")
        rows.append(one)

    # largeur visible (sans ANSI)
    import re
    def vis_len(x: str) -> int: return len(re.sub(r"\x1b\[[0-9;]*m","",x))
    width = [max(vis_len(r[i]) for r in [header]+rows) for i in range(len(header))]

    def fmt(row: List[str]) -> str:
        out=[]
        for i,v in enumerate(row):
            w=width[i]
            if "\x1b[" in v:
                plain = re.sub(r"\x1b\[[0-9;]*m","",v)
                v = v.replace(plain, _center(plain,w))
            else:
                v = _center(v,w)
            out.append(v)
        return " | ".join(out)

    sep = ["-"*w for w in width]
    table = "\n".join([fmt(header), fmt(sep), *[fmt(r) for r in rows]])
    return table, states

# ============================================================
# Actions AUTO (refresh / backtest / promote)
# ============================================================

def _run(args: List[str]) -> int:
    p = subprocess.run(args, capture_output=True, text=True)
    out = (p.stdout or "").strip(); err = (p.stderr or "").strip()
    if out: print(out)
    if err: print(err)
    return p.returncode

def _refresh_tf(tf: str, limit: int) -> None:
    _run(["python","-m","jobs.refresh_pairs","--timeframe",tf,"--top","0","--backfill-tfs",tf,"--limit",str(limit)])

def _backtest_promote(tfs: List[str]) -> None:
    _run(["python","-m","jobs.backtest","--from-watchlist","--tfs",",".join(tfs)])
    _run(["python","-m","jobs.promote","--backup"])

# ============================================================
# Boucle
# ============================================================

async def run_orchestrator(ex, run_cfg: RunConfig, notifier=None, command_stream=None) -> None:
    cfg = load_config()
    trade_cfg = (cfg.get("trading") or {})
    exec_enabled = bool(trade_cfg.get("exec_enabled", False))
    max_pairs = int(trade_cfg.get("max_pairs", 10))

    while True:
        try:
            strats = load_strategies()
            table, states = _render(run_cfg.symbols, run_cfg.tfs, run_cfg.data_dir, strats)

            print("\x1b[2J\x1b[H", end="")
            print("=== ORCHESTRATOR ===")
            print(f"timeframes={','.join(run_cfg.tfs)} refresh={run_cfg.refresh_secs}s exec_enabled={int(exec_enabled)}")
            print(table)

            # ---------- AUTO ----------
            if run_cfg.auto:
                # 1) refresh par TF si au moins un MIS/OLD
                for tf in run_cfg.tfs:
                    if any(states[(s,tf)][0] in ("MIS","OLD") for s in run_cfg.symbols if (s,tf) in states):
                        print(f"[auto] refresh tf={tf}")
                        _refresh_tf(tf, run_cfg.limit)

                # 2) backtest+promote si au moins un DAT (data ok mais pas de strat)
                if any(lbl=="DAT" for lbl,_ in states.values()):
                    print("[auto] backtest + promote")
                    _backtest_promote(run_cfg.tfs)

            # ---------- exécution signaux seulement sur VERT ----------
            active: List[Tuple[str,str]] = [(s,tf) for (s,tf),(lbl,c) in states.items() if lbl=="OK "]
            if max_pairs>0: active = active[:max_pairs]
            print(f"[orchestrator] actifs={len(active)} / {len(run_cfg.symbols)*len(run_cfg.tfs)} -> " +
                  (", ".join(f"{_short(s)}:{tf}" for s,tf in active) if active else "(aucun)"))

            # placeholder d’évaluation (observe-only si exec_disabled)
            async def _eval_one(sym:str, tf:str, strat:Dict[str,Any]):
                try:
                    from engine.signals.executor import evaluate_tick  # optionnel
                except Exception:
                    evaluate_tick = None  # type: ignore
                if evaluate_tick:
                    await maybe_await(evaluate_tick(ex, sym, tf, strat, exec_enabled))
                else:
                    print(f"[observe] {_short(sym)}:{tf} • ema_f={strat.get('ema_fast')} ema_s={strat.get('ema_slow')}")

            tasks=[]
            for s,tf in active:
                strat = strats.get(f"{s}:{tf}")
                if not strat: continue
                tasks.append(asyncio.create_task(_eval_one(s, tf, strat)))
            if tasks:
                await asyncio.gather(*tasks)

        except Exception as e:
            print(f"[orchestrator] erreur: {e}")

        await asyncio.sleep(max(1, int(run_cfg.refresh_secs)))

async def maybe_await(x):
    if hasattr(x, "__await__"): return await x
    return x

# ============================================================
# Aide : construire une RunConfig depuis la conf
# ============================================================

def run_config_from_yaml() -> RunConfig:
    cfg = load_config()
    rt = cfg.get("runtime", {}) or {}
    wl = cfg.get("watchlist", {}) or {}
    mt = cfg.get("maintainer", {}) or {}

    # symbols = top de la watchlist (sinon fallback)
    wl_doc = load_watchlist()
    syms = [(d.get("symbol") or "").replace("_","").upper() for d in (wl_doc.get("top") or []) if d.get("symbol")]
    if not syms:
        syms = ["BTCUSDT","ETHUSDT","SOLUSDT"]

    tfs = [str(x) for x in (wl.get("backfill_tfs") or ["1m","5m","15m"])]
    return RunConfig(
        symbols=syms,
        tfs=tfs,
        refresh_secs=int(mt.get("live_interval_secs", 5)),
        data_dir=str(rt.get("data_dir") or "/notebooks/scalp_data/data"),
        limit=int(wl.get("backfill_limit", 1500)),
        auto=True,
    )