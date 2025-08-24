# scalper/selfcheck.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

def _missing_secrets(cfg: Dict[str, Any]) -> List[str]:
    miss: List[str] = []
    if not (cfg.get("secrets", {}).get("bitget", {}).get("access")):
        miss.append("BITGET_ACCESS_KEY")
    if not (cfg.get("secrets", {}).get("bitget", {}).get("secret")):
        miss.append("BITGET_SECRET_KEY")
    # passphrase peut être vide selon le compte → on ne la force pas
    return miss

def _missing_config(cfg: Dict[str, Any]) -> List[str]:
    req: List[str] = []
    rt = (cfg.get("runtime") or {})
    strat = (cfg.get("strategy") or {})
    if not strat.get("live_timeframe"):
        req.append("strategy.live_timeframe")
    if not rt.get("data_dir"):
        req.append("runtime.data_dir")
    return req

def preflight_or_die(verbose: bool = False) -> None:
    """
    Valide secrets (.env) + paramètres généraux (config.yaml).
    Écrit un green‑flag persistant si tout est OK.
    """
    from scalper.config.loader import load_config
    cfg = load_config()

    miss_sec = _missing_secrets(cfg)
    miss_cfg = _missing_config(cfg)

    issues: List[str] = []
    if miss_sec:
        issues.append("Secrets manquants: " + ", ".join(miss_sec))
    if miss_cfg:
        issues.append("Paramètres manquants: " + ", ".join(miss_cfg))

    if issues:
        for i in issues:
            print("[-]", i)
        raise SystemExit(1)

    # Green flag
    ready = Path("/notebooks/.scalper/READY.json")
    ready.parent.mkdir(parents=True, exist_ok=True)
    ready.write_text(
        json.dumps({"status": "ok", "reason": "preflight"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if verbose:
        print(f"[✓] Préflight OK — ready flag écrit: {ready}")