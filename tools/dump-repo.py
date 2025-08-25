#!/usr/bin/env python3
# tools/dump-repo.py
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
from pathlib import Path
from typing import Iterable, Iterator, List, Tuple

# ---------- Réglages ----------
EXCLUDE_DIRS = {
    ".git", "__pycache__", ".ipynb_checkpoints",
    "scalp_data", "data", "dumps", ".venv", "venv", ".mypy_cache",
    "build", "dist", ".pytest_cache", ".idea", ".vscode",
}
EXCLUDE_FILES_GLOB = {
    "*.pyc", "*.pyo", "*.so", "*.dll", "*.dylib",
    ".env", "*.env", "*.log", "*.sqlite*", "*.db",
}
# un fichier > cette taille est lu en mode "ligne rapide"
SAFE_READ_MAX = 5_000_000  # 5 Mo
# "vieux" fichiers proposés à la corbeille
STALE_DAYS = 120

# ---------- Utils ----------
def is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    name = path.name
    for pat in EXCLUDE_FILES_GLOB:
        if path.match(pat):
            return True
    return False

def iter_files(root: Path) -> Iterator[Path]:
    for p in root.rglob("*"):
        if p.is_file() and not is_excluded(p.relative_to(root)):
            yield p

def try_read_text(p: Path) -> Tuple[int, bool]:
    """
    Retourne (line_count, is_text).
    Lecture tolérante; ne lit pas > SAFE_READ_MAX octets en entier.
    """
    try:
        sz = p.stat().st_size
        if sz == 0:
            return (0, True)
        if sz > SAFE_READ_MAX:
            # comptage lignes rapide: lit par chunks
            n = 0
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(64 * 1024), b""):
                    n += chunk.count(b"\n")
            return (n if n else 1, True)
        # essai lecture texte
        txt = p.read_text(encoding="utf-8", errors="ignore")
        # compter les lignes
        return (txt.count("\n") + (1 if txt and not txt.endswith("\n") else 0), True)
    except Exception:
        return (0, False)

def sha1_of_small(p: Path, max_bytes: int = 1_000_000) -> str:
    h = hashlib.sha1()
    try:
        with p.open("rb") as f:
            h.update(f.read(max_bytes))
        return h.hexdigest()
    except Exception:
        return "NA"

def human(n: int) -> str:
    for unit in ["B","KB","MB","GB"]:
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}"
        n /= 1024.0
    return f"{n:.0f}B"

def rel(root: Path, p: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")

# ---------- Dump ----------
def build_dump(root: Path) -> str:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    lines: List[str] = []
    lines.append(f"# DUMP REPO")
    lines.append(f"# root: {root}")
    lines.append(f"# when: {now}")
    lines.append("# note: exclude .git, dumps/, scalp_data/…")
    lines.append("")

    # TREE
    lines.append("=== TREE ===")
    all_paths = sorted(rel(root, p) for p in iter_files(root))
    for path in all_paths:
        lines.append(path)
    lines.append("")

    # FILES
    lines.append("=== FILES ===")
    total_size = 0
    total_lines = 0
    file_rows: List[Tuple[str,int,int,str,str]] = []  # path, size, nlines, mtime, sha1
    for p in sorted(iter_files(root)):
        st = p.stat()
        size = st.st_size
        mtime = dt.datetime.utcfromtimestamp(st.st_mtime).isoformat() + "Z"
        nlines, is_text = try_read_text(p)
        h1 = sha1_of_small(p) if size <= SAFE_READ_MAX else sha1_of_small(p, 256_000)
        file_rows.append((rel(root,p), size, nlines, mtime, h1))
        total_size += size
        total_lines += nlines

    # écriture
    lines.append("path | size | lines | mtime_utc | sha1")
    for path, size, nlines, mtime, h1 in file_rows:
        lines.append(f"{path} | {size} | {nlines} | {mtime} | {h1}")
    lines.append("")

    # SUMMARY
    lines.append("=== SUMMARY ===")
    lines.append(f"files={len(file_rows)}")
    lines.append(f"bytes={total_size} ({human(total_size)})")
    lines.append(f"lines={total_lines}")
    lines.append("")

    # CANDIDATES (trash)
    lines.append("=== TRASH_CANDIDATES ===")
    # 1) fichiers très vieux
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=STALE_DAYS)
    stale = [r for r in file_rows if dt.datetime.fromisoformat(r[3].rstrip("Z")) < cutoff]
    for path, size, nlines, mtime, _ in stale:
        lines.append(f"STALE>{STALE_DAYS}d | {path} | {human(size)} | {nlines} | {mtime}")
    # 2) vides
    empties = [r for r in file_rows if r[1] == 0]
    for path, size, nlines, mtime, _ in empties:
        lines.append(f"EMPTY | {path}")
    # 3) checkpoints / artefacts
    artefacts = [r for r in file_rows if "/.ipynb_checkpoints/" in r[0] or r[0].endswith("-checkpoint.py")]
    for path, *_ in artefacts:
        lines.append(f"ARTEFACT | {path}")
    lines.append("")

    return "\n".join(lines)

def main() -> int:
    ap = argparse.ArgumentParser(description="Dump texte propre du repo (sans data/dumps/git).")
    ap.add_argument("--root", default=".", help="Racine du repo (défaut: .)")
    ap.add_argument("--outdir", default="dumps", help="Dossier où écrire le dump (défaut: dumps/)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    outdir = (root / args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    out = outdir / f"DUMP_{ts}.txt"

    txt = build_dump(root)
    out.write_text(txt, encoding="utf-8")
    print(f"[dump] écrit: {out} ({len(txt.splitlines())} lignes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())