"""Utilities for managing the Scalp bot version."""
from __future__ import annotations

from pathlib import Path
import re

# Path to the VERSION file within the package
_VERSION_FILE = Path(__file__).resolve().parent / "VERSION"
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def get_version() -> str:
    """Return the current version of the bot.

    If the VERSION file does not exist the default version ``0.0.0`` is
    returned.
    """
    if not _VERSION_FILE.exists():
        return "0.0.0"
    return _VERSION_FILE.read_text().strip()


def _parse(version: str) -> tuple[int, int, int]:
    match = _VERSION_RE.match(version)
    if not match:
        raise ValueError(f"Invalid version: {version!r}")
    return tuple(int(x) for x in match.groups())


def bump_version(part: str = "patch") -> str:
    """Bump the version stored in the VERSION file.

    Parameters
    ----------
    part:
        Which component to increment. Accepted values are ``"major"``,
        ``"minor"`` and ``"patch"`` (default).
    """
    major, minor, patch = _parse(get_version())
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    new_version = f"{major}.{minor}.{patch}"
    _VERSION_FILE.write_text(new_version)
    return new_version
