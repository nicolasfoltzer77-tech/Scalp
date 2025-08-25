#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dump texte compact du dépôt 'scalp' uniquement.

- Racine par défaut: /notebooks/scalp
- Exclut caches, logs, dumps, notebooks, binaires, images, etc.
- N'inclut que le code/config lisible (.py, .sh, .yaml/.yml, .toml, .ini, .txt, .md)
- Tronque à N lignes par fichier (par défaut 1200)
- Saute les fichiers > M octets (par défaut 300 KB)
- Écrit dans /notebooks/dumps/DUMP_YYYYMMDD-HHMMSS.txt
- En fin de fichier: TOP des gros fichiers exclus (diagnostic)

Usage:
  python scalp/tools/dump-repo.py
  python scalp/tools/dump-repo.py --root /notebooks/scalp --max-lines 1500 --max-bytes 300000
"""

from __future__ import annotations
import argparse
import fnmatch
import os
import sys
import time
from pathlib import Path
from typing import Iterable, List, Tuple

# ------------------ options CLI ------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Dump texte compact du repo scalp")
    ap.add_argument("--root", default="/notebooks/scalp",
                    help="Racine à dumper (défaut: /notebooks/scalp)")
    ap.add_argument("--out-dir", default="/notebooks/dumps",
                    help="Dossier de sortie du dump (défaut: /notebooks/dumps)")
    ap.add_argument("--max-lines", type=int, default=1200,
                    help="Nombre max de lignes par fichier (défaut: 1200)")
    ap.add_argument("--max-bytes", type=int, default=300_000,
                    help="Taille max d'un fichier inclus (défaut: 300000)")
    ap.add_argument("--no-diag", action="store_true",
                    help="Ne pas lister les gros fichiers exclus en fin de dump")
    return ap.parse_args()

# ------------------ filtres ------------------

EXCLUDE_DIRS = {
    ".git", ".github", ".vscode", ".idea",
    "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ipynb_checkpoints", "build", "dist",
    "dumps", "dump", "backups",
    # anciens répertoires d'essais éventuels
    "scalp0", "scalp1", "scalp2", "scalp3",
}

EXCLUDE_GLOBS = [
    # données & archives
    "*.csv", "*.parquet", "*.feather",
    "*.log", "*.gz", "*.zip", "*.xz", "*.bz2",
    # binaires / images / docs lourds
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg",
    "*.pdf", "*.so", "*.dll", "*.dylib", "*.bin",
    # notebooks
    "*.ipynb",
]

# extensions “texte” autorisées
ALLOW_EXT = {
    ".py", ".sh", ".yaml", ".yml", ".toml", ".ini",
    ".txt", ".md",
}

# ------------------ helpers ------------------

def _match_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)

def _is_text_file(p: Path) -> bool:
    """Heuristique simple pour fichiers sans extension: petit et sans NULL byte."""
    try:
        if p.stat().st_size > 128_000:
            return False
        with p.open("rb") as f:
            blob = f.read(4096)
        return b"\0" not in blob
    except Exception:
        return False

def _allowed_file(p: Path) -> bool:
    if _match_any(p.name, EXCLUDE_GLOBS):
        return False
    if p.suffix in ALLOW_EXT:
        return True
    # autoriser scripts sans extension si “texte”
    return _is_text_file(p)

def _is_excluded_dir(path: Path, root: Path) -> bool:
    # Exclure si l'un des segments est dans EXCLUDE_DIRS
    try:
        rel_parts = path.relative_to(root).parts
    except Exception:
        return True
    return any(part in EXCLUDE_DIRS for part in rel_parts)

def _iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_dir():
            # on ne peut pas “pruner” rglob, on filtrera au moment d'inclure
            continue
        yield p

def _read_head(p: Path, limit: int) -> List[str]:
    out: List[str] = []
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                out.append(line.rstrip("\n"))
                if i >= limit:
                    out.append(f"... [trunc {p.name} at {limit} lines]")
                    break
    except Exception as e:
        out = [f"[!] lecture impossible: {e}"]
    return out

# ------------------ main ------------------

def main() -> int:
    args = parse_args()
    ROOT = Path(args.root).resolve()
    if not ROOT.exists():
        print(f"[!] Racine introuvable: {ROOT}", file=sys.stderr)
        return 2

    OUT_DIR = Path(args.out_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    OUT = OUT_DIR / f"DUMP_{stamp}.txt"

    excluded_big: List[Tuple[int, str]] = []
    kept_count = 0

    with OUT.open("w", encoding="utf-8") as w:
        w.write(f"# DUMP du repo (root={ROOT})\n")
        w.write(f"# Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        w.write(f"# Filtres: exclude_dirs={sorted(EXCLUDE_DIRS)}\n")
        w.write(f"#          exclude_globs={EXCLUDE_GLOBS}\n")
        w.write(f"#          allow_ext={sorted(ALLOW_EXT)}\n")
        w.write(f"#          max_lines_per_file={args.max_lines}  max_file_bytes={args.max_bytes}\n\n")

        for p in _iter_files(ROOT):
            # exclure .env réel
            if p.name == ".env":
                continue

            # exclure si le chemin traverse un dossier ignoré
            if _is_excluded_dir(p.parent, ROOT):
                continue

            # filtrage par motif/extension
            if not _allowed_file(p):
                try:
                    size = p.stat().st_size
                    if size > 50_000:
                        excluded_big.append((size, str(p.relative_to(ROOT))))
                except Exception:
                    pass
                continue

            # garde-fou: taille max
            try:
                st = p.stat()
            except FileNotFoundError:
                continue

            if st.st_size > args.max_bytes:
                excluded_big.append((st.st_size, str(p.relative_to(ROOT))))
                continue

            kept_count += 1
            rel = p.relative_to(ROOT)
            w.write(f"\n\n# ==== {rel} ({st.st_size} bytes) ====\n")
            for line in _read_head(p, args.max_lines):
                w.write(line + "\n")

        # diagnostic des gros exclus
        if not args.no_diag and excluded_big:
            excluded_big.sort(reverse=True)
            w.write("\n\n# ---- DIAGNOSTIC: GROS FICHIERS EXCLUS ----\n")
            for size, path in excluded_big[:50]:
                w.write(f"{size:>10d}  {path}\n")

    # comptage des lignes du dump pour affichage
    try:
        with OUT.open("r", encoding="utf-8") as f:
            total_lines = sum(1 for _ in f)
    except Exception:
        total_lines = -1

    print(f"[dump] écrit: {OUT} ({total_lines if total_lines>=0 else '?'} lignes) • fichiers inclus: {kept_count}")
    return 0

if __name__ == "__main__":
    sys.exit(main())