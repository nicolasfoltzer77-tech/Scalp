"""Utilities and helpers for Scalp bot.

This module also looks for a ``.env`` file located one directory above the
repository (e.g. ``Notebooks/.env`` when the project lives in
``Notebooks/scalp``) and loads any variables found there.  This allows users to
store private API keys outside of the git repository while still making them
available to the bot at runtime.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_parent_env() -> None:
    """Load environment variables from ``../.env`` if present."""

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
