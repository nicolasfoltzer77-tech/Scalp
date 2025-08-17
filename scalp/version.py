"""Utilities for managing the Scalp bot version."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

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
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown part: {part}")
    new_version = f"{major}.{minor}.{patch}"
    _VERSION_FILE.write_text(f"{new_version}\n")
    return new_version


def bump_version_from_message(message: str) -> str:
    """Bump the version according to a commit message.

    ``message`` is evaluated using a tiny subset of the Conventional
    Commits spec. Messages starting with ``feat`` bump the *minor*
    version, messages whose header ends with ``!`` or contain
    ``BREAKING CHANGE`` bump the *major* version. All other messages
    bump the *patch* component.
    """

    header = message.strip().splitlines()[0].lower()
    lower = message.lower()
    type_part = header.split(":")[0]
    if "!" in type_part or "breaking change" in lower:
        part = "major"
    elif type_part.startswith("feat"):
        part = "minor"
    else:
        part = "patch"
    return bump_version(part)


def bump_version_from_git() -> str:
    """Read the latest git commit message and bump the version accordingly."""
    try:
        message = subprocess.check_output(
            ["git", "log", "-1", "--pretty=%B"], text=True
        ).strip()
    except Exception:
        message = ""
    return bump_version_from_message(message)


if __name__ == "__main__":
    print(bump_version_from_git())
