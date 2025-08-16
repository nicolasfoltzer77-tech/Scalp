#!/usr/bin/env python3
"""Install all project dependencies.

Run this script once to install every ``requirements*.txt`` file found in the
repository as well as the packages needed for the test suite.  All subsequent
invocations of the bot or its submodules will then share the same Python
environment with the required dependencies available.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def install_packages(*args: str) -> None:
    """Install packages using pip for the current Python interpreter."""
    cmd = [sys.executable, "-m", "pip", "install", *args]
    subprocess.check_call(cmd)


def main() -> None:
    repo_root = Path(__file__).resolve().parent

    # Install from any requirements*.txt file across the repository so that
    # sub-packages with their own dependency lists are also covered.
    for req in sorted(repo_root.rglob("requirements*.txt")):
        install_packages("-r", str(req))

    # Ensure test dependencies are available
    install_packages("pytest")


if __name__ == "__main__":
    main()
