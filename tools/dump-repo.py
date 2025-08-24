#!/usr/bin/env python3
"""
ops/dump_repo.py

Génère un dump complet du repo :
- timestamp dans le nom
- arborescence des fichiers
- date de dernière modification
- contenu intégral des fichiers texte avec numéros de ligne
- exclut les répertoires inutiles (git, cache, trash, dumps)
- garde uniquement le dernier dump (supprime les anciens)

Usage :
    python ops/dump_repo.py
"""

from __future__ import annotations
import datetime as dt
import os
import sys
from pathlib import Path

# Racine du repo = parent d'ops/
REPO_ROOT = Path(__file__).resolve().parents[1]
DUMP_DIR = REPO_ROOT / "dumps"
DUMP_DIR.mkdir(parents=True, exist_ok=True)

TS = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_PATH = DUMP_DIR / f"DUMP_{TS}.txt"

# Extensions/fichiers à ignorer (binaires ou inutiles)
IGNORE_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf",
    ".pkl", ".db", ".sqlite", ".zip", ".tar", ".gz",
    ".pyc", ".pyo",
}
IGNORE_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", "dumps"}
IGNORE_PREFIX = {"TRASH_"}

def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in IGNORE_EXT:
        return False
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            if b"\x00" in chunk:
                return False
        return True
    except Exception:
        return False

def write_header(f, title: str) -> None:
    f.write("\n" + "=" * 80 + "\n")
    f.write(f"{title}\n")
    f.write("=" * 80 + "\n")

def dump_tree(root: Path, f) -> None:
    write_header(f, "ARBORESCENCE")
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if any(str(rel).startswith(pref) for pref in IGNORE_PREFIX):
            continue
        if p.is_file():
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{rel}  (last modified: {mtime})\n")
        else:
            f.write(str(rel) + "/\n")

def dump_files(root: Path, f) -> None:
    write_header(f, "FICHIERS COMPLETS")
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_dir():
            continue
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if any(str(rel).startswith(pref) for pref in IGNORE_PREFIX):
            continue
        if not is_text_file(p):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            f.write(f"\n[!!] Impossible de lire {rel}: {e}\n")
            continue
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        f.write("\n" + "-" * 80 + "\n")
        f.write(f"FILE: {rel}  (last modified: {mtime})\n")
        f.write("-" * 80 + "\n")
        for i, line in enumerate(content, 1):
            f.write(f"{i:6d}: {line}\n")

def prune_old_dumps() -> None:
    dumps = sorted(DUMP_DIR.glob("DUMP_*.txt"))
    for old in dumps:
        if old != OUT_PATH:  # on ne garde que le nouveau
            try:
                old.unlink()
                print(f"[x] Ancien dump supprimé: {old.name}")
            except Exception as e:
                print(f"[!] Impossible de supprimer {old}: {e}")

def main() -> int:
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(f"# DUMP {TS}\nRepo: {REPO_ROOT}\n")
        dump_tree(REPO_ROOT, f)
        dump_files(REPO_ROOT, f)
    prune_old_dumps()
    print(f"[✓] Dump écrit: {OUT_PATH}")
    return 0

if __name__ == "__main__":
    sys.exit(main())