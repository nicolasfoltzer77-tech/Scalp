"""Tests for loading environment variables from ``notebook/.env``."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def test_parent_env_loaded(tmp_path, monkeypatch) -> None:
    """Module should load variables from ``notebook/.env`` if present."""

    notebook = tmp_path / "notebook"
    spot = notebook / "spot"
    spot.mkdir(parents=True)
    mexc_bot = spot / "mexc_bot.py"
    mexc_bot.write_text("")
    env_file = notebook / ".env"
    env_file.write_text("MEXC_ACCESS_KEY=from_env\n")

    old = os.environ.pop("MEXC_ACCESS_KEY", None)
    monkeypatch.setattr(sys, "argv", [str(mexc_bot)])
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
