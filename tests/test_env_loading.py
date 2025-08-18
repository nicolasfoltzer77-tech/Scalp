"""Tests for loading environment variables from parent .env file."""

from __future__ import annotations

import importlib
import os
from pathlib import Path


def test_parent_env_loaded(tmp_path) -> None:
    """Module should load variables from ``../.env`` if present."""

    parent = Path(__file__).resolve().parents[2]
    env_file = parent / ".env"
    env_file.write_text("MEXC_ACCESS_KEY=from_env\n")

    # Ensure any previous value is cleared then reload the package to trigger
    # the loading logic.
    old = os.environ.pop("MEXC_ACCESS_KEY", None)
    import scalp

    importlib.reload(scalp)

    try:
        assert os.getenv("MEXC_ACCESS_KEY") == "from_env"
    finally:
        env_file.unlink(missing_ok=True)
        if old is None:
            os.environ.pop("MEXC_ACCESS_KEY", None)
        else:
            os.environ["MEXC_ACCESS_KEY"] = old
