from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    import yaml
except Exception:
    yaml = None

# Aliases ENV -> clés canoniques (SECRETS UNIQUEMENT)
_ALIASES: Dict[str, Tuple[str, ...]] = {
    "BITGET_ACCESS_KEY": ("BITGET_API_KEY", "BITGET_KEY"),
    "BITGET_SECRET_KEY": ("BITGET_API_SECRET", "BITGET_SECRET"),
    "BITGET_PASSPHRASE": ("BITGET_API_PASSPHRASE", "BITGET_PASSWORD", "BITGET_API_PASSWORD"),
    "TELEGRAM_BOT_TOKEN": ("TELEGRAM_TOKEN", "TG_TOKEN"),
    "TELEGRAM_CHAT_ID": ("TG_CHAT_ID", "TELEGRAM_TO", "CHAT_ID"),
}

def _adopt_alias(target: str) -> None:
    if os.getenv(target):
        return
    for alt in _ALIASES.get(target, ()):
        v = os.getenv(alt)
        if v:
            os.environ[target] = v
            return

def apply_env_aliases() -> None:
    for k in _ALIASES:
        _adopt_alias(k)

def _default_paths() -> Dict[str, str]:
    data_root = os.getenv("DATA_ROOT", "/notebooks/scalp_data")  # HORS REPO
    root = Path(data_root)
    return {
        "data_dir": str(root / "data"),
        "log_dir": str(root / "logs"),
        "reports_dir": str(root / "reports"),
    }

def load_yaml_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parent / "config.yaml"
    path = Path(path)
    if yaml is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}

def load_config(path: str | os.PathLike | None = None) -> Dict[str, Any]:
    cfg = load_yaml_config(path)
    apply_env_aliases()

    # Secrets depuis .env parent (sitecustomize.py les charge)
    cfg.setdefault("secrets", {})
    cfg["secrets"]["bitget"] = {
        "access": os.getenv("BITGET_ACCESS_KEY") or "",
        "secret": os.getenv("BITGET_SECRET_KEY") or "",
        "passphrase": os.getenv("BITGET_PASSPHRASE") or "",
    }
    cfg["secrets"]["telegram"] = {
        "token": os.getenv("TELEGRAM_BOT_TOKEN") or "",
        "chat_id": os.getenv("TELEGRAM_CHAT_ID") or "",
    }

    # Chemins hors repo
    defaults = _default_paths()
    r = cfg.setdefault("runtime", {})
    r.setdefault("data_dir", defaults["data_dir"])
    r.setdefault("log_dir", defaults["log_dir"])
    r.setdefault("reports_dir", defaults["reports_dir"])
    r.setdefault("paper_trade", True)
    r.setdefault("allowed_symbols", [])
    r.setdefault("refresh_secs", 5)

    s = cfg.setdefault("strategy", {})
    s.setdefault("live_timeframe", "1m")

    return cfg