"""Test configuration and shared fixtures."""

import sys
import types
from pathlib import Path


# Ensure the project root is importable so tests can ``import bot``.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# Provide a dummy ``requests`` module so ``bot.py`` doesn't attempt to install
# the real dependency during test collection. Individual tests patch the
# functions they need (``request``/``post``/``get``).
sys.modules.setdefault(
    "requests",
    types.SimpleNamespace(HTTPError=Exception, request=None, post=None, get=None),
)

