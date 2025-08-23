# scalp/config/loader.py
from __future__ import annotations
import os, json
from typing import Any, Dict, Tuple

# YAML est recommandé, mais on fallback proprement si PyYAML n'est pas installé
try:
    import yaml  # type: ignore
except Exception:
    yaml = None  # fallback JSON si besoin

# dotenv (facultatif) pour charger un .env automatiquement
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

# ---------------- Utils ----------------

def _parse_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool): return x
    s = str(x).strip().lower()
    if s in ("1","true","yes","y","on"): return True
    if s in ("0","false","no","n","off",""): return False
    return default

def _parse_float(x: Any, default: float | None = None) -> float | None:
    try: return float(x)
    except Exception: return default

def _parse_int(x: Any, default: int | None = None) -> int | None:
    try: return int(str(x).strip())
    except Exception: return default

def _parse_csv(x: Any) -> list[str]:
    if x is None: return []
    if isinstance(x, (list, tuple)): return [str(v).strip() for v in x if str(v).strip()]
    return [t.strip() for t in str(x).replace(" ", "").split(",") if t.strip()]

def _read_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        if yaml:
            return yaml.safe_load(f) or {}
        # fallback JSON si quelqu’un met du JSON dans config.yml (rare mais safe)
        try:
            return json.load(f)
        except Exception:
            raise RuntimeError(f"Impossible de lire {path}: installe PyYAML (`pip install pyyaml`) ou fournis du JSON valide.")

def _merge_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    # shallow merge suffisant ici (structure plate)
    out = dict(a)
    out.update({k: v for k, v in b.items() if v is not None})
    return out

# ---------------- Public API ----------------

def load_settings(
    config_path: str = "config.yml",
    config_local_path: str = "config.local.yml",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Retourne (config_runtime, secrets) :
      - config_runtime : paramètres de stratégie / exécution (OK pour versionner)
      - secrets        : clés API & tokens (NE PAS versionner)
    Priorité : config.yml < config.local.yml < ENV (non sensibles)
    Secrets proviennent EXCLUSIVEMENT de l'ENV (.env)
    """
    # 1) .env (pour secrets & env non sensibles). Faculatif.
    if load_dotenv is not None:
        load_dotenv(override=False)

    # 2) Charge YAML (config.yml + override local)
    base = _read_yaml(config_path)
    local = _read_yaml(config_local_path)
    cfg = _merge_dict(base, local)

    # 3) Overlay ENV **non sensibles** (permet de surcharger sans toucher au YAML)
    env_overlay: Dict[str, Any] = {}
    # Verbosité
    env_overlay["QUIET"] = _parse_bool(os.getenv("QUIET", cfg.get("QUIET", 0)), bool(cfg.get("QUIET", 0)))
    env_overlay["PRINT_OHLCV_SAMPLE"] = _parse_bool(os.getenv("PRINT_OHLCV_SAMPLE", cfg.get("PRINT_OHLCV_SAMPLE", 0)),
                                                    bool(cfg.get("PRINT_OHLCV_SAMPLE", 0)))
    # Runtime / Stratégie
    env_overlay["TIMEFRAME"] = os.getenv("TIMEFRAME", cfg.get("TIMEFRAME", "5m"))
    env_overlay["CASH"] = _parse_float(os.getenv("CASH", cfg.get("CASH", 10000)), cfg.get("CASH", 10000))
    env_overlay["RISK_PCT"] = _parse_float(os.getenv("RISK_PCT", cfg.get("RISK_PCT", 0.5)), cfg.get("RISK_PCT", 0.5))
    env_overlay["SLIPPAGE_BPS"] = _parse_float(os.getenv("SLIPPAGE_BPS", cfg.get("SLIPPAGE_BPS", 0)), cfg.get("SLIPPAGE_BPS", 0))
    # Watchlist
    env_overlay["WATCHLIST_MODE"] = os.getenv("WATCHLIST_MODE", cfg.get("WATCHLIST_MODE", "static"))
    env_overlay["WATCHLIST_LOCAL_CONC"] = _parse_int(
        os.getenv("WATCHLIST_LOCAL_CONC", cfg.get("WATCHLIST_LOCAL_CONC", 4)), cfg.get("WATCHLIST_LOCAL_CONC", 4)
    )
    env_overlay["TOP_SYMBOLS"] = _parse_csv(os.getenv("TOP_SYMBOLS", cfg.get("TOP_SYMBOLS")))
    env_overlay["TOP_CANDIDATES"] = _parse_csv(os.getenv("TOP_CANDIDATES", cfg.get("TOP_CANDIDATES")))
    # Caps (optionnel) : on accepte YAML (dict) ou ENV JSON
    caps_env = os.getenv("CAPS_JSON")
    if caps_env:
        try:
            env_overlay["CAPS"] = json.loads(caps_env)
        except Exception:
            env_overlay["CAPS"] = cfg.get("CAPS", {})
    else:
        env_overlay["CAPS"] = cfg.get("CAPS", {})

    # 4) Secrets UNIQUEMENT via ENV (jamais via YAML)
    secrets = {
        "BITGET_API_KEY": os.getenv("BITGET_API_KEY", ""),
        "BITGET_API_SECRET": os.getenv("BITGET_API_SECRET", ""),
        "BITGET_API_PASSWORD": os.getenv("BITGET_API_PASSWORD", ""),
        "BITGET_USE_TESTNET": _parse_bool(os.getenv("BITGET_USE_TESTNET", os.getenv("BITGET_TESTNET", "1")), True),
        "BITGET_PRODUCT": os.getenv("BITGET_PRODUCT", "umcbl"),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
    }

    # 5) Runtime normalisé pour l’orchestrateur
    runtime = {
        "quiet": bool(env_overlay["QUIET"]),
        "print_sample": bool(env_overlay["PRINT_OHLCV_SAMPLE"]),
        "timeframe": str(env_overlay["TIMEFRAME"]),
        "cash": float(env_overlay["CASH"]),
        "risk_pct": float(env_overlay["RISK_PCT"]),
        "slippage_bps": float(env_overlay["SLIPPAGE_BPS"]),
        "watchlist_mode": str(env_overlay["WATCHLIST_MODE"]),
        "watchlist_local_conc": int(env_overlay["WATCHLIST_LOCAL_CONC"]),
        "top_symbols": env_overlay["TOP_SYMBOLS"],          # list[str]
        "top_candidates": env_overlay["TOP_CANDIDATES"],    # list[str]
        "caps": env_overlay["CAPS"],                        # dict
        # rempli au boot par les frais Bitget
        "fees_by_symbol": {}, 
    }

    return runtime, secrets