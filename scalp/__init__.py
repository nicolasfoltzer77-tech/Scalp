"""Utilities and helpers for Scalp bot."""

from .version import get_version, bump_version_from_message

__all__ = ["get_version", "bump_version_from_message", "__version__"]

__version__ = get_version()
