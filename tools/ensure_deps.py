#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import importlib.util, subprocess, sys

def _is_installed(modname: str) -> bool:
    return importlib.util.find_spec(modname) is not None

def ensure(pkg_to_mod: dict[str, str]) -> dict[str, bool]:
    """
    pkg_to_mod: mapping 'pip-package' -> 'python_module'
    Installe via pip les packages dont le module n'est pas importable.
    Retourne un dict {pip-package: True/False} selon install OK.
    """
    res = {}
    for pip_name, modname in pkg_to_mod.items():
        if _is_installed(modname):
            res[pip_name] = True
            continue
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--no-input", pip_name])
            res[pip_name] = _is_installed(modname)
        except Exception:
            res[pip_name] = False
    return res