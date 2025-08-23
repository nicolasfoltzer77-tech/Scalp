"""Utilities and helpers for Scalp bot.

When the bot is executed from ``notebook/spot/bitget_bot.py`` it expects secret
keys to live in ``notebook/.env``.  On import this module attempts to load the
variables from that file so that API keys can remain outside of the repository
yet still be available at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _load_parent_env() -> None:
    """Load environment variables from ``../.env`` relative to the entry script.

    The bot is typically launched from ``notebook/spot/bitget_bot.py`` and keys
    are expected to be stored one directory above (``notebook/.env``).  If that
    file is not found the function falls back to the historical behaviour of
    checking ``../.env`` relative to the package itself.
    """

    script_path = Path(sys.argv[0]).resolve()
    env_file = script_path.parent.parent / ".env"
    if not env_file.exists():
        env_file = Path(__file__).resolve().parents[2] / ".env"
        if not env_file.exists():
            return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_file)
    except Exception:  # pragma: no cover - optional dependency
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_parent_env()

from .version import get_version, bump_version_from_message  # noqa: E402
from .strategy import (  # noqa: E402
    Signal,
    scan_pairs,
    select_active_pairs,
    generate_signal,
    backtest,
)
from .risk.manager import RiskManager  # noqa: E402

__all__ = [
    "get_version",
    "bump_version_from_message",
    "__version__",
    "Signal",
    "scan_pairs",
    "select_active_pairs",
    "generate_signal",
    "RiskManager",
    "backtest",
]

__version__ = get_version()
