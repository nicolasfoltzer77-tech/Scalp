# engine/config/strategies.py
from __future__ import annotations
import json, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Tuple

_STRAT_PATH = Path(__file__).resolve().parent / "strategies.yml"

_DEF_TTL_BARS = {  # fallback si meta absent
    "DEFAULT": 300,
    "LOW": 1000,
    "MEDIUM": 500,
    "HIGH": 250,
    "EXPERIMENTAL": 120,
}

def _parse_iso(s: str | None) -> datetime | None:
    if not s: return None
    try:
        if s.endswith("Z"): s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except Exception:
        return None

def _pair_tf(key: str) -> Tuple[str, str]:
    # "BTCUSDT:1m" -> ("BTCUSDT","1m")
    if ":" in key:
        a, b = key.split(":", 1)
        return a.replace("_","").upper(), b
    return key.replace("_","").upper(), "1m"

def _tf_minutes(tf: str) -> float:
    tf = tf.strip().lower()
    if tf.endswith("m"): return float(tf[:-1] or 1)
    if tf.endswith("h"): return float(tf[:-1] or 1) * 60.0
    if tf.endswith("d"): return float(tf[:-1] or 1) * 60.0 * 24.0
    # défaut: 1m
    return 1.0

def _load_doc() -> Dict[str, Any]:
    if not _STRAT_PATH.exists(): return {"meta": {}, "strategies": {}}
    try:
        return json.loads(_STRAT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"meta": {}, "strategies": {}}

def _policy_bars(meta: Dict[str, Any], risk_label: str) -> int:
    # 1) meta.ttl_policy_bars
    pol = meta.get("ttl_policy_bars") if isinstance(meta, dict) else None
    if not isinstance(pol, dict): pol = {}
    # 2) env overrides (STRAT_TTL_<RISK>=nb)
    env_key = f"STRAT_TTL_{risk_label.upper()}"
    if os.getenv(env_key):
        try:
            return max(1, int(float(os.getenv(env_key, "0"))))
        except Exception:
            pass
    # 3) table meta/par défaut
    return int(pol.get(risk_label.upper(), pol.get("DEFAULT", _DEF_TTL_BARS.get(risk_label.upper(), _DEF_TTL_BARS["DEFAULT"]))))

def _global_mult(meta: Dict[str, Any]) -> float:
    try:
        m = float(meta.get("ttl_global_multiplier", 1.0))
        env = os.getenv("STRAT_TTL_MULTIPLIER")
        if env is not None:
            m *= float(env)
        return max(0.01, m)
    except Exception:
        return 1.0

def load_strategies() -> Dict[str, Dict[str, Any]]:
    """
    Retourne {"PAIR:TF": { params..., 'expired': bool, 'executable': bool, 'ttl_hours': float }}
    TTL = (ttl_bars OU policy[risk]) * durée_barre(tf)
    """
    doc = _load_doc()
    meta = doc.get("meta") or {}
    src = doc.get("strategies") or {}
    mult = _global_mult(meta)

    now = datetime.now(timezone.utc)
    out: Dict[str, Dict[str, Any]] = {}

    for k, v in src.items():
        if not isinstance(v, dict): continue
        pair, tf = _pair_tf(k)
        tf_min = _tf_minutes(str(tf))
        risk = (v.get("risk_label") or "DEFAULT").upper()

        # nombre de barres de validité
        bars = int(v.get("ttl_bars")) if isinstance(v.get("ttl_bars"), (int, float, str)) and str(v.get("ttl_bars")).strip() else _policy_bars(meta, risk)
        bars = max(1, int(bars * mult))

        ttl_hours = (bars * tf_min) / 60.0
        last = _parse_iso(str(v.get("last_validated") or ""))

        expired = True
        if last is not None:
            expired = now > (last + timedelta(hours=ttl_hours))

        execute_flag = bool(v.get("execute", False))
        risk_label = (v.get("risk_label") or "").upper()
        # on ne décide pas ici pour EXPERIMENTAL; l'orchestrateur peut autoriser via env
        executable = execute_flag and not expired and risk_label != "EXPERIMENTAL"

        out[f"{pair}:{tf}"] = {
            **v,
            "pair": pair,
            "tf": tf,
            "risk_label": risk_label,
            "ttl_bars": bars,
            "ttl_hours": ttl_hours,
            "expired": expired,
            "executable": executable,
        }
    return out

def executable_keys(*, allow_experimental: bool = False) -> Dict[str, Dict[str, Any]]:
    all_ = load_strategies()
    out: Dict[str, Dict[str, Any]] = {}
    for k, s in all_.items():
        if s.get("expired"): continue
        if not s.get("execute"): continue
        if s.get("risk_label") == "EXPERIMENTAL" and not allow_experimental:
            continue
        out[k] = s
    return out