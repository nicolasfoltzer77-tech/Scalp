import os, yaml
from pathlib import Path

def load_config(path: str | None = None) -> dict:
    """Charge config.yaml + ENV secrets"""
    if path is None:
        path = Path(__file__).resolve().parent / "config.yaml"
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    # Injecte secrets depuis ENV
    cfg["secrets"] = {
        "bitget": {
            "access": os.getenv("BITGET_ACCESS_KEY"),
            "secret": os.getenv("BITGET_SECRET_KEY"),
            "passphrase": os.getenv("BITGET_PASSPHRASE"),
        },
        "telegram": {
            "token": os.getenv("TELEGRAM_BOT_TOKEN"),
            "chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        }
    }
    return cfg