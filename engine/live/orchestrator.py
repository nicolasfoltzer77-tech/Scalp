# engine/live/orchestrator.py
from __future__ import annotations

import asyncio
import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Sequence

from engine.config.loader import load_config
from engine.live.notify import listing_ok, bot_started

@dataclass
class RunConfig:
    symbols: Sequence[str]
    timeframe: str
    refresh_secs: int
    cache_dir: str

# ---------- helpers IO ----------

def _live_paths(cache_dir: str) -> Dict[str, Path]:
    live_dir = Path(cache_dir) / "live"
    logs_dir = live_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return {
        "live_dir": live_dir,
        "logs_dir": logs_dir,
        "signals_csv": logs_dir / "signals.csv",
        "orders_csv": live_dir / "orders.csv",
    }

def _append_signals(signals_csv: Path, rows: Iterable[Sequence]) -> None:
    write_header = not signals_csv.exists()
    with signals_csv.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["ts", "symbol", "price", "tf"])
        w.writerows(rows)

# ---------- modes ----------

async def _mode_heartbeat(ex, run_cfg: RunConfig) -> None:
    """Boucle minimale quand aucune stratégie exécutable n'est disponible."""
    paths = _live_paths(run_cfg.cache_dir)
    last_notify = 0.0
    while True:
        ts = int(time.time() * 1000)
        rows = []
        for sym in run_cfg.symbols:
            try:
                px = ex.get_last_price(sym)
            except Exception:
                px = 0.0
            rows.append([ts, sym, px, run_cfg.timeframe])
        _append_signals(paths["signals_csv"], rows)
        if time.time() - last_notify > 30:
            listing_ok(run_cfg.symbols)
            last_notify = time.time()
        await asyncio.sleep(max(1, int(run_cfg.refresh_secs)))

async def _mode_trading(ex, run_cfg: RunConfig, strategies: Dict[str, Dict], notifier, cmd_stream):
    """
    Ici brancher ta boucle trading existante (trader, risk manager, etc.).
    Cette implémentation minimale se contente du heartbeat tant que le code
    trading n'est pas collé ici.
    """
    await _mode_heartbeat(ex, run_cfg)

# ---------- orchestrateur ----------

def _has_executable_strategies(strategies: Dict[str, Dict]) -> bool:
    """Une stratégie est exécutable si execute=true ET que l'utilisateur autorise les untested si besoin."""
    if not strategies:
        return False
    allow_untested = os.getenv("ALLOW_UNTESTED_STRATEGY", "").lower() in {"1", "true", "yes"}
    for _k, s in strategies.items():
        execute = bool(s.get("execute", False))
        risk_label = (s.get("risk_label") or "").upper()
        if execute and (risk_label != "EXPERIMENTAL" or allow_untested):
            return True
    return False

async def run_orchestrator(ex, run_cfg: RunConfig, notifier, cmd_stream):
    cfg = load_config()
    promoted: Dict[str, Dict] = (cfg.get("strategy") or {}).get("promoted", {})
    # prise en charge du fichier JSON .yml si présent (engine/config/strategies.yml)
    try:
        strat_yml = Path(__file__).resolve().parents[1] / "config" / "strategies.yml"
        if strat_yml.exists():
            import json
            doc = json.loads(strat_yml.read_text(encoding="utf-8"))
            promoted = doc.get("strategies") or promoted
    except Exception:
        pass

    # notifier le démarrage
    bot_started(timeframe=run_cfg.timeframe, symbols=run_cfg.symbols, strategies=len(promoted or {}))

    # si aucune stratégie exécutable => observe‑only (heartbeat)
    if not _has_executable_strategies(promoted or {}):
        # on reste en lecture prix + logs, sans ordres
        await _mode_heartbeat(ex, run_cfg)
        return

    # sinon, on passe au mode trading (ton implémentation)
    await _mode_trading(ex, run_cfg, promoted, notifier, cmd_stream)