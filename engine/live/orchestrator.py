# engine/live/orchestrator.py
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from engine.config.loader import load_config
from engine.config.strategies import load_strategies
from engine.backtest.loader_csv import load_csv_ohlcv  # pour vérifier fraicheur des données

# ============================================================
# Config & Modèle
# ============================================================

@dataclass
class RunConfig:
    symbols: List[str]
    timeframe: str
    refresh_secs: int
    cache_dir: str  # data_dir (ohlcv csv)

# minutes par TF
_TF_MIN = {"1m":1, "5m":5, "15m":15, "1h":60, "4h":240, "1d":1440}

def _tf_minutes(tf: str) -> int:
    return _TF_MIN.get(str(tf), 1)

# ============================================================
# Helpers statut (identiques à la sémantique maintainer)
# ============================================================

def _last_bar_ts_ms(cache_dir: str, symbol: str, tf: str) -> Optional[int]:
    try:
        rows = load_csv_ohlcv(cache_dir, symbol, tf, max_rows=1)
        if rows:
            return int(rows[-1][0])
    except Exception:
        pass
    return None

def _data_is_fresh(now_ms: int, last_ms: Optional[int], tf: str) -> bool:
    if last_ms is None:
        return False
    tf_ms = _tf_minutes(tf) * 60_000
    # tolérance 2×TF
    return (now_ms - last_ms) <= (2 * tf_ms)

def _strat_is_valid(strategies: Dict[str, Dict[str, Any]], symbol: str, tf: str) -> bool:
    key = f"{symbol}:{tf}"
    s = strategies.get(key)
    return bool(s) and not bool(s.get("expired"))

def _status_cell(cache_dir: str, strategies: Dict[str, Dict], symbol: str, tf: str) -> Tuple[str, str]:
    """
    Retourne (label, color):
      ('MIS','black')  = données manquantes
      ('OLD','red')    = données présentes mais trop vieilles
      ('DAT','orange') = données ok, stratégie absente/expirée
      ('OK ','green')  = données + stratégie valides
    """
    now = int(time.time() * 1000)
    last_ms = _last_bar_ts_ms(cache_dir, symbol, tf)
    if last_ms is None:
        return ("MIS", "black")
    if not _data_is_fresh(now, last_ms, tf):
        return ("OLD", "red")
    if _strat_is_valid(strategies, symbol, tf):
        return ("OK ", "green")
    return ("DAT", "orange")

# ============================================================
# Affichage compact
# ============================================================

_COLORS = {
    "black": "\x1b[30m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "orange": "\x1b[33m",
    "reset": "\x1b[0m",
}

def _short_sym(s: str) -> str:
    s = s.upper().replace("_", "")
    return s[:-4] if s.endswith("USDT") else s

def _center(text: str, width: int) -> str:
    pad = max(0, width - len(text))
    return " " * (pad // 2) + text + " " * (pad - pad // 2)

def _render_table(symbols: List[str], tf: str, cache_dir: str, strategies: Dict[str, Dict]) -> str:
    header = ["PAIR", tf]
    rows: List[List[str]] = []
    for s in symbols:
        lbl, color = _status_cell(cache_dir, strategies, s, tf)
        cell = f"{_COLORS.get(color,'')}{lbl}{_COLORS['reset']}"
        rows.append([_short_sym(s), cell])

    # largeur visible (sans ANSI)
    import re
    def vis_len(x: str) -> int:
        return len(re.sub(r"\x1b\[[0-9;]*m", "", x))

    widths = [
        max(vis_len(r[i]) for r in ([header] + rows))
        for i in range(len(header))
    ]

    def fmt(row: List[str]) -> str:
        out = []
        for i, v in enumerate(row):
            w = widths[i]
            if "\x1b[" in v:
                plain = re.sub(r"\x1b\[[0-9;]*m", "", v)
                v = v.replace(plain, _center(plain, w))
            else:
                v = _center(v, w)
            out.append(v)
        return " | ".join(out)

    sep = ["-" * w for w in widths]
    return "\n".join([fmt(header), fmt(sep), *[fmt(r) for r in rows]])

# ============================================================
# Stratégies actives & évaluation
# ============================================================

def _active_universe(symbols: Iterable[str], tf: str, cache_dir: str,
                     strategies: Dict[str, Dict]) -> List[str]:
    """
    Garde uniquement les paires VERTES (data fraîche + stratégie non expirée).
    """
    out: List[str] = []
    for s in symbols:
        lbl, color = _status_cell(cache_dir, strategies, s, tf)
        if color == "green":
            out.append(s)
    return out

async def _eval_signals_one(ex, symbol: str, tf: str, strat_cfg: Dict[str, Any],
                            exec_enabled: bool) -> None:
    """
    Placeholder d'évaluation. Essaie d'appeler un moteur si présent :
      - engine.signals.executor.evaluate_tick(ex, symbol, tf, strat_cfg, exec=bool)
    Sinon: log minimal (observe‑only).
    """
    # Import tardif (facultatif)
    try:
        from engine.signals.executor import evaluate_tick  # type: ignore
    except Exception:
        evaluate_tick = None  # type: ignore

    if evaluate_tick:
        try:
            await maybe_await(evaluate_tick(ex, symbol, tf, strat_cfg, exec_enabled))
            return
        except Exception as e:
            print(f"[orchestrator] evaluate_tick error {symbol}:{tf} -> {e}")

    # Fallback observe-only
    print(f"[orchestrator] observe {symbol}:{tf} • ema_f={strat_cfg.get('ema_fast')} ema_s={strat_cfg.get('ema_slow')}")

async def maybe_await(x):
    if hasattr(x, "__await__"):
        return await x
    return x

def _strategy_for(strategies: Dict[str, Dict], symbol: str, tf: str) -> Optional[Dict[str, Any]]:
    return strategies.get(f"{symbol}:{tf}")

# ============================================================
# Orchestrateur
# ============================================================

async def run_orchestrator(ex, run_cfg: RunConfig, notifier=None, command_stream=None) -> None:
    """
    Boucle principale :
      1) Charge les stratégies (engine/config/strategies.yml)
      2) Filtre l'univers (VERT uniquement)
      3) Itère toutes les refresh_secs : affiche tableau compact + évalue signaux
    """
    cfg = load_config()
    tf = run_cfg.timeframe
    cache_dir = run_cfg.cache_dir
    refresh = max(1, int(run_cfg.refresh_secs))

    # trading config (observe-only par défaut)
    trade_cfg = (cfg.get("trading") or {})
    exec_enabled = bool(trade_cfg.get("exec_enabled", False))  # false par défaut
    max_pairs = int(trade_cfg.get("max_pairs", 10))            # limite de sécurité

    # boucle
    while True:
        try:
            # 1) état courant
            strategies = load_strategies()  # { "SYMBOL:TF": {..., expired:bool, ...} }
            table = _render_table(run_cfg.symbols, tf, cache_dir, strategies)
            print("\x1b[2J\x1b[H", end="")  # clear + home
            print("=== ORCHESTRATOR ===")
            print(f"timeframe={tf} refresh={refresh}s exec_enabled={int(exec_enabled)}")
            print(table)

            # 2) univers VERT
            active = _active_universe(run_cfg.symbols, tf, cache_dir, strategies)
            if max_pairs > 0:
                active = active[:max_pairs]
            print(f"[orchestrator] actifs={len(active)} / {len(run_cfg.symbols)} -> {', '.join(_short_sym(s) for s in active) or '(aucun)'}")

            # 3) évaluer les signaux (observe‑only si exec_enabled=False)
            tasks = []
            for s in active:
                strat = _strategy_for(strategies, s, tf)
                if not strat or bool(strat.get("expired")):
                    continue
                tasks.append(asyncio.create_task(_eval_signals_one(ex, s, tf, strat, exec_enabled)))

            if tasks:
                await asyncio.gather(*tasks)

        except Exception as e:
            print(f"[orchestrator] erreur: {e}")

        await asyncio.sleep(refresh)