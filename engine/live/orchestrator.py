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
# Modèle / Config d'exécution
# ============================================================

@dataclass
class RunConfig:
    symbols: List[str]        # univers (watchlist)
    tfs: List[str]            # colonnes (1m,5m,15m,…)
    refresh_secs: int         # cadence d’affichage/évaluation
    data_dir: str             # répertoire OHLCV csv
    limit: int                # profondeur lors des backfills
    auto: bool = True         # automation (refresh, backtest, promote)
    fresh_mult: float = 1.0   # “fraîche” si âge <= fresh_mult × TF
    cooldown_secs: int = 60   # anti-tempête pour actions AUTO par TF

_TF_MIN = {"1m":1, "5m":5, "15m":15, "1h":60, "4h":240, "1d":1440}

def _tf_minutes(tf: str) -> int:
    return _TF_MIN.get(str(tf), 1)

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
# Statut / Couleurs (console)
# ============================================================

_COL = {"k":"\x1b[30m","r":"\x1b[31m","g":"\x1b[32m","o":"\x1b[33m","x":"\x1b[0m"}

def _short(sym: str) -> str:
    sym = sym.upper().replace("_","")
    return sym[:-4] if sym.endswith("USDT") else sym

def _is_fresh(now_ms: int, last_ms: Optional[int], tf: str, fresh_mult: float) -> bool:
    if last_ms is None: return False
    return (now_ms - last_ms) <= (fresh_mult * _tf_minutes(tf) * 60_000)

def _status_cell(data_dir: str, strats: Dict[str, Dict], symbol: str, tf: str, fresh_mult: float) -> Tuple[str,str]:
    """
    Retourne (label, color_code):
      MIS / k  : pas de données
      OLD / r  : données présentes mais pas fraîches
      DAT / o  : données fraîches, pas de stratégie
      OK  / g  : données fraîches + stratégie valide
    """
    now = int(time.time()*1000)
    last = _last_ts_ms(data_dir, symbol, tf)
    if last is None:
        return ("MIS","k")
    if not _is_fresh(now, last, tf, fresh_mult):
        return ("OLD","r")
    if _strat_valid(strats, symbol, tf):
        return ("OK ","g")
    return ("DAT","o")

# ============================================================
# Rendu tableau multi‑TF
# ============================================================

def _center(t: str, w: int) -> str:
    pad = max(0, w - len(t))
    return " "*(pad//2) + t + " "*(pad - pad//2)

def _render(symbols: List[str], tfs: List[str], data_dir: str, strats: Dict[str,Dict], fresh_mult: float
           ) -> Tuple[str, Dict[Tuple[str,str], Tuple[str,str]], Dict[str,int]]:
    header = ["PAIR", *tfs]
    rows: List[List[str]] = []
    states: Dict[Tuple[str,str], Tuple[str,str]] = {}
    counts = {"k":0,"r":0,"o":0,"g":0}

    for s in symbols:
        one = [_short(s)]
        for tf in tfs:
            lbl, col = _status_cell(data_dir, strats, s, tf, fresh_mult)
            states[(s,tf)] = (lbl, col)
            counts[col] = counts.get(col,0) + 1
            one.append(f"{_COL[col]}{lbl}{_COL['x']}")
        rows.append(one)

    # largeur visible (strip ANSI)
    import re
    def vis_len(x: str) -> int: return len(re.sub(r"\x1b\[[0-9;]*m","",x))
    width = [max(vis_len(r[i]) for r in [header] + rows) for i in range(len(header))]

    def fmt(row: List[str]) -> str:
        out=[]
        for i,v in enumerate(row):
            w=width[i]
            if "\x1b[" in v:
                plain = re.sub(r"\x1b\[[0-9;]*m","",v)
                v = v.replace(plain, _center(plain, w))
            else:
                v = _center(v, w)
            out.append(v)
        return " | ".join(out)

    sep = ["-"*w for w in width]
    table = "\n".join([fmt(header), fmt(sep), *[fmt(r) for r in rows]])
    return table, states, counts

# ============================================================
# AUTO actions (refresh / backtest / promote) avec cooldown
# ============================================================

_last_auto: Dict[str, float] = {}  # par clé (refresh:TF, backtest)

def _cool(key: str, cooldown: int) -> bool:
    now = time.time()
    t0 = _last_auto.get(key, 0.0)
    if (now - t0) >= cooldown:
        _last_auto[key] = now
        return True
    return False

def _run(args: List[str]) -> int:
    p = subprocess.run(args, capture_output=True, text=True)
    out = (p.stdout or "").strip(); err = (p.stderr or "").strip()
    if out: print(out)
    if err: print(err)
    return p.returncode

def _auto_refresh(tf: str, limit: int, cooldown: int) -> None:
    key = f"refresh:{tf}"
    if not _cool(key, cooldown):
        return
    print(f"[auto] refresh tf={tf}")
    _run(["python","-m","jobs.refresh_pairs","--timeframe",tf,"--top","0","--backfill-tfs",tf,"--limit",str(limit)])

def _auto_backtest_promote(tfs: List[str], cooldown: int) -> None:
    key = "backtest"
    if not _cool(key, cooldown):
        return
    print("[auto] backtest + promote")
    _run(["python","-m","jobs.backtest","--from-watchlist","--tfs",",".join(tfs)])
    _run(["python","-m","jobs.promote","--backup"])

# ============================================================
# Boucle orchestrateur
# ============================================================

async def run_orchestrator(ex, run_cfg: RunConfig, notifier=None, command_stream=None) -> None:
    cfg = load_config()
    trade_cfg = (cfg.get("trading") or {})
    exec_enabled = bool(trade_cfg.get("exec_enabled", False))
    max_pairs = int(trade_cfg.get("max_pairs", 12))

    first_legend = True

    while True:
        try:
            strats = load_strategies()
            table, states, counts = _render(run_cfg.symbols, run_cfg.tfs, run_cfg.data_dir, strats, run_cfg.fresh_mult)

            # clear + home
            print("\x1b[2J\x1b[H", end="")
            print("=== ORCHESTRATOR ===")
            print(f"timeframes={','.join(run_cfg.tfs)} refresh={run_cfg.refresh_secs}s exec_enabled={int(exec_enabled)}")
            if first_legend:
                print("legend: "
                      f"{_COL['k']}MIS{_COL['x']}=no data • "
                      f"{_COL['r']}OLD{_COL['x']}=stale • "
                      f"{_COL['o']}DAT{_COL['x']}=data no strat • "
                      f"{_COL['g']}OK{_COL['x']}=ready")
                first_legend = False
            print(table)
            print(f"stats • MIS={counts['k']} OLD={counts['r']} DAT={counts['o']} OK={counts['g']}")

            # ---------- AUTO ----------
            if run_cfg.auto:
                # refresh par TF si présence de MIS/OLD
                for tf in run_cfg.tfs:
                    if any(states.get((s,tf),("",""))[0] in ("MIS","OLD") for s in run_cfg.symbols):
                        _auto_refresh(tf, run_cfg.limit, run_cfg.cooldown_secs)

                # backtest+promote si on observe au moins un DAT
                if any(lbl=="DAT" for lbl,_c in states.values()):
                    _auto_backtest_promote(run_cfg.tfs, run_cfg.cooldown_secs)

            # ---------- Actifs (VERT uniquement) ----------
            active: List[Tuple[str,str]] = [(s,tf) for (s,tf),(lbl,c) in states.items() if lbl=="OK "]
            if max_pairs > 0:
                active = active[:max_pairs]
            if active:
                pairs = ", ".join(f"{_short(s)}:{tf}" for s,tf in active)
            else:
                pairs = "(aucun)"
            print(f"[orchestrator] actifs={len(active)} / {len(run_cfg.symbols)*len(run_cfg.tfs)} -> {pairs}")

            # Placeholder d'évaluation (observe-only si exec disabled)
            async def _eval_one(sym: str, tf: str, strat: Dict[str,Any]):
                try:
                    from engine.signals.executor import evaluate_tick  # optionnel
                except Exception:
                    evaluate_tick = None  # type: ignore
                if evaluate_tick:
                    await maybe_await(evaluate_tick(ex, sym, tf, strat, exec_enabled))
                else:
                    print(f"[observe] {_short(sym)}:{tf} • ema_f={strat.get('ema_fast')} ema_s={strat.get('ema_slow')}")

            tasks: List[asyncio.Task] = []
            for s,tf in active:
                st = strats.get(f"{s}:{tf}")
                if not st: continue
                tasks.append(asyncio.create_task(_eval_one(s, tf, st)))
            if tasks:
                await asyncio.gather(*tasks)

        except Exception as e:
            print(f"[orchestrator] erreur: {e}")

        await asyncio.sleep(max(1, int(run_cfg.refresh_secs)))

async def maybe_await(x):
    if hasattr(x, "__await__"): return await x
    return x

# ============================================================
# Fabrique de RunConfig à partir de config.yml
# ============================================================

def run_config_from_yaml() -> RunConfig:
    cfg = load_config()
    rt = cfg.get("runtime", {}) or {}
    wl = cfg.get("watchlist", {}) or {}
    mt = cfg.get("maintainer", {}) or {}
    auto_cfg = (cfg.get("auto") or {})  # section optionnelle pour ce module

    # univers = top watchlist (sinon fallback)
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
        auto=bool(auto_cfg.get("enabled", True)),
        fresh_mult=float(auto_cfg.get("fresh_mult", mt.get("fresh_mult", 1.0))),
        cooldown_secs=int(auto_cfg.get("cooldown_secs", 60)),
    )