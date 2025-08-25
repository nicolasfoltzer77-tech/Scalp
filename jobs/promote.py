#!/usr/bin/env python3
# jobs/promote.py
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

from engine.config.loader import load_config

# ---------- utils paths ----------

def _paths() -> Tuple[Path, Path, Path]:
    cfg = load_config()
    rt = cfg.get("runtime", {})
    reports_dir = Path(rt.get("reports_dir") or "/notebooks/scalp_data/reports")
    draft = reports_dir / "strategies.yml.next"
    final = Path(__file__).resolve().parents[1] / "engine" / "config" / "strategies.yml"
    backups = reports_dir / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    return draft, final, backups

def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}

def _write_json_atomic(path: Path, doc: Dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    tmp.replace(path)

# ---------- TTL helpers ----------

# mapping TF -> minutes
_TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}

def _tf_minutes(tf: str) -> int:
    return _TF_MIN.get(str(tf), 1)

def _default_ttl_mult(tf: str) -> int:
    """
    Multiplicateur de TTL par TF.
    Ajuste si tu veux être plus/moins strict.
    """
    if tf == "1m":   return 240     # 4h
    if tf == "5m":   return 240     # 20h
    if tf == "15m":  return 192     # 2j
    if tf == "1h":   return 168     # 1 semaine
    return 240

def _is_expired(created_at_ms: int, tf: str, ttl_mult: int | None = None) -> bool:
    now_ms = int(time.time() * 1000)
    mult = _default_ttl_mult(tf) if ttl_mult is None else int(ttl_mult)
    ttl_min = mult * _tf_minutes(tf)
    return now_ms - int(created_at_ms or 0) > ttl_min * 60_000

# ---------- merge/promotion ----------

def _promote(draft_doc: Dict, current_doc: Dict, ttl_mult_cfg: Dict[str, int]) -> Tuple[Dict, Dict]:
    """
    Retourne (merged, summary)
    - merged: nouveau document final {"strategies": {...}}
    - summary: stats de promotion
    """
    merged: Dict[str, Dict] = {"strategies": {}}
    cur = (current_doc.get("strategies") or {})
    new = (draft_doc.get("strategies") or {})

    added = updated = kept = expired = 0
    now_ms = int(time.time() * 1000)

    # 1) intégrer toutes les entrées actuelles
    for key, val in cur.items():
        merged["strategies"][key] = dict(val)
        kept += 1

    # 2) injecter / écraser avec le draft
    for key, val in new.items():
        # key format "SYMBOL:TF"
        tf = key.split(":")[1] if ":" in key else "1m"
        # TTL bars (optionnel) -> converti en created_at/expired
        created = int(val.get("created_at") or now_ms)
        ttl_mult = ttl_mult_cfg.get(tf)
        is_old = _is_expired(created, tf, ttl_mult=ttl_mult)
        val2 = dict(val)
        val2["created_at"] = created
        val2["expired"] = bool(is_old)

        if key in merged["strategies"]:
            merged["strategies"][key].update(val2)
            updated += 1
        else:
            merged["strategies"][key] = val2
            added += 1
        if is_old:
            expired += 1

    summary = {
        "added": added,
        "updated": updated,
        "kept": kept,
        "expired": expired,
        "total": len(merged["strategies"]),
    }
    return merged, summary

def _ttl_cfg_from_config() -> Dict[str, int]:
    """
    Permet de surcharger le multiplicateur TTL par TF via config.yaml:
      maintainer:
        ttl_mult:
          1m: 240
          5m: 240
          15m: 192
          1h: 168
    """
    try:
        cfg = load_config()
        mt = cfg.get("maintainer", {}) or {}
        ttl = mt.get("ttl_mult") or {}
        return {str(k): int(v) for k, v in ttl.items()}
    except Exception:
        return {}

# ---------- CLI ----------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Promote strategies.yml.next -> strategies.yml (merge + TTL)")
    ap.add_argument("--draft", type=str, default=None,
                    help="Chemin du draft (par défaut: reports/strategies.yml.next)")
    ap.add_argument("--final", type=str, default=None,
                    help="Chemin du fichier final (par défaut: engine/config/strategies.yml)")
    ap.add_argument("--backup", action="store_true", help="Sauvegarde du fichier final avant écrasement")
    ns = ap.parse_args(argv)

    draft_def, final_def, backups_dir = _paths()
    draft_path = Path(ns.draft or draft_def)
    final_path = Path(ns.final or final_def)

    if not draft_path.exists():
        print(f"[promote] draft introuvable: {draft_path}")
        return 1

    draft_doc = _read_json(draft_path)
    current_doc = _read_json(final_path)

    # sauvegarde
    if ns.backup and final_path.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        bkp = backups_dir / f"strategies.{ts}.json"
        shutil.copy2(final_path, bkp)
        print(f"[promote] backup -> {bkp}")

    ttl_cfg = _ttl_cfg_from_config()
    merged, summary = _promote(draft_doc, current_doc, ttl_cfg)

    # écriture atomique
    final_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(final_path, merged)

    # trace humaine
    add, upd, kept, expd, tot = (summary[k] for k in ("added","updated","kept","expired","total"))
    print(f"[promote] OK • added={add} • updated={upd} • kept={kept} • expired={expd} • total={tot}")
    print(f"[promote] => {final_path}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())