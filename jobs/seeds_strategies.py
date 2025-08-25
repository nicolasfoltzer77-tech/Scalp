#!/usr/bin/env python3
# jobs/seed_strategies.py
"""
Génère/actualise engine/config/strategies.yml à partir de la watchlist.

- Crée pour chaque symbole de la watchlist une stratégie EXPERIMENTAL
  (execute=false => observe-only) sur les TF demandés.
- TTL basé sur un nombre de barres (ttl_policy_bars) par niveau de risque.
- Merge non destructif par défaut (garde les entrées déjà présentes, sauf --overwrite).

Exemples:
  # seed pour 1m seulement, observe-only
  python jobs/seed_strategies.py --tfs 1m

  # seed 1m,5m pour les 15 1ers symboles de la watchlist
  python jobs/seed_strategies.py --tfs 1m,5m --top 15

  # forcer overwrite complet du fichier (remplace tout)
  python jobs/seed_strategies.py --tfs 1m,5m --overwrite
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from engine.config.loader import load_config

# ---------- chemins ----------
def _paths() -> Dict[str, Path]:
    cfg = load_config()
    rt = cfg.get("runtime", {})
    reports_dir = Path(rt.get("reports_dir") or "/notebooks/scalp_data/reports")
    watchlist = reports_dir / "watchlist.yml"  # JSON lisible
    strat_yml = Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"
    return {"watchlist": watchlist, "strategies": strat_yml}

# ---------- IO ----------
def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_json(path: Path, doc: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

# ---------- core ----------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _normalize_symbol(s: str) -> str:
    return (s or "").replace("_", "").upper()

def seed_from_watchlist(tfs: List[str], top: int | None, overwrite: bool, ttl_bars_exp:int) -> int:
    P = _paths()
    wl = _read_json(P["watchlist"])
    if not wl:
        print(f"[seed] Watchlist introuvable ou vide: {P['watchlist']}")
        return 2

    symbols = [_normalize_symbol(d.get("symbol","")) for d in (wl.get("top") or []) if d.get("symbol")]
    if top:
        symbols = symbols[:top]
    if not symbols:
        print("[seed] Aucun symbole valide dans la watchlist.")
        return 3

    # doc courant (merge) ou nouveau
    if overwrite or not P["strategies"].exists():
        doc = {
            "meta": {
                "generated_at": _now_iso(),
                "note": "EXPERIMENTAL: observe-only (execute=false). TTL en nb de barres.",
                "ttl_policy_bars": {
                    "DEFAULT": 300, "LOW": 1000, "MEDIUM": 500, "HIGH": 250, "EXPERIMENTAL": ttl_bars_exp
                },
                "ttl_global_multiplier": 1.0
            },
            "strategies": {}
        }
    else:
        doc = _read_json(P["strategies"]) or {"meta": {}, "strategies": {}}
        doc.setdefault("meta", {}).setdefault("ttl_policy_bars", {"DEFAULT": 300, "EXPERIMENTAL": ttl_bars_exp})
        doc["meta"]["generated_at"] = _now_iso()
        doc["meta"].setdefault("ttl_global_multiplier", 1.0)

    strategies = doc.setdefault("strategies", {})

    created = 0
    for sym in symbols:
        for tf in tfs:
            key = f"{sym}:{tf}"
            # on n’écrase pas les entrées existantes sauf --overwrite
            if not overwrite and key in strategies:
                continue
            strategies[key] = {
                "name": "BASE_UNTESTED",
                "risk_label": "EXPERIMENTAL",
                "execute": False,                 # observe-only
                "ema_fast": 9,
                "ema_slow": 21,
                "atr_period": 14,
                "trail_atr_mult": 1.5,
                "risk_pct_equity": 0.005,
                "last_validated": _now_iso(),     # marquage initial
                # facultatif : forcer un TTL spécifique pour EXPERIMENTAL
                "ttl_bars": ttl_bars_exp
            }
            created += 1

    _write_json(P["strategies"], doc)
    print(f"[seed] OK • {created} entrées écrites • fichier: {P['strategies']}")
    return 0

# ---------- main ----------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Seed strategies.yml depuis la watchlist")
    ap.add_argument("--tfs", type=str, default="1m", help="Liste de TF séparés par des virgules (ex: 1m,5m,15m)")
    ap.add_argument("--top", type=int, default=0, help="Limiter aux N premiers de la watchlist (0=illimité)")
    ap.add_argument("--overwrite", action="store_true", help="Remplace entièrement les entrées existantes")
    ap.add_argument("--ttl-bars-exp", type=int, default=120, help="TTL (nb de barres) pour EXPERIMENTAL")
    ns = ap.parse_args(argv)

    tfs = [t.strip() for t in ns.tfs.split(",") if t.strip()]
    top = int(ns.top) if ns.top and ns.top > 0 else None
    return seed_from_watchlist(tfs=tfs, top=top, overwrite=ns.overwrite, ttl_bars_exp=int(ns.ttl_bars_exp))

if __name__ == "__main__":
    raise SystemExit(main())