#!/usr/bin/env python3
# scalp/tools/dump-repo.py
# ------------------------------------------------------------
# Dump ultra-simple et rapide du dossier *notebooks/scalp* :
#  - écrit un dump texte dans /notebooks/dumps
#  - liste les fichiers utiles (code & conf), exclus les artefacts
#  - pour chaque fichier : chemin relatif, nb lignes, date modif
#  - résumé final : nb fichiers & total lignes
# ------------------------------------------------------------

from __future__ import annotations
import sys, io, os, time
from pathlib import Path
from datetime import datetime

# --- Réglages simples (modifiables) -----------------------------------------
ROOT = Path("/notebooks/scalp")                  # dossier à dumper
OUT_DIR = Path("/notebooks/scalp/dumps/")               # où écrire le dump
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Extensions considérées "texte utile"
ALLOW_EXT = {".py", ".yml", ".yaml", ".sh", ".txt", ".md", ".ini", ".cfg"}

# Dossiers ignorés (par nom de dossier)
EXCLUDE_DIRS = {
    ".git", ".github", ".idea", ".vscode",
    ".ipynb_checkpoints", "__pycache__", ".mypy_cache", ".pytest_cache",
    "backups", "dumps", "dump", "build", "dist",
    "dash", "tests", "scalp0", "scalp1", "scalp2", "scalp3",
    "engine/backtest",   # lourd & optionnel
}

# Motifs de fichiers à ignorer (globs simples par suffixe)
EXCLUDE_SUFFIX = {
    ".csv", ".parquet", ".feather", ".log",
    ".gz", ".zip", ".xz", ".bz2",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
    ".ipynb",
}

# --- Implémentation ----------------------------------------------------------
def is_excluded(path: Path) -> bool:
    # exclut si un segment de chemin est dans EXCLUDE_DIRS
    parts = path.relative_to(ROOT).parts
    # gestion des chemins "engine/backtest" (deux segments)
    if len(parts) >= 2 and f"{parts[0]}/{parts[1]}" in EXCLUDE_DIRS:
        return True
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    # exclut par suffixe (fichiers binaires / volumineux)
    if path.suffix.lower() in EXCLUDE_SUFFIX:
        return True
    return False

def count_lines(p: Path) -> int:
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def fmt_mtime(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "1970-01-01 00:00:00"

def main() -> int:
    if not ROOT.exists():
        print(f"[!] Dossier introuvable : {ROOT}", file=sys.stderr)
        return 2

    # nom de fichier de sortie simple, sans réinclure d’anciens dumps
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = OUT_DIR / f"DUMP_{stamp}.txt"

    files_info = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if is_excluded(p):
            continue
        if p.suffix.lower() not in ALLOW_EXT:
            continue
        rel = p.relative_to(ROOT)
        nlines = count_lines(p)
        mtime = fmt_mtime(p.stat().st_mtime)
        files_info.append((str(rel), nlines, mtime))

    files_info.sort()  # tri alpha par chemin

    total_lines = sum(n for _, n, _ in files_info)
    total_files = len(files_info)

    # écriture du dump (texte brut, lisible)
    buf = io.StringIO()
    buf.write("# ---- DUMP SCALP (simple) ----\n")
    buf.write(f"time        : {fmt_mtime(time.time())}\n")
    buf.write(f"root       : {ROOT}\n")
    buf.write(f"out        : {out_path}\n")
    buf.write(f"allow_ext  : {', '.join(sorted(ALLOW_EXT))}\n")
    buf.write(f"exclude_dirs: {', '.join(sorted(EXCLUDE_DIRS))}\n")
    buf.write(f"exclude_suf: {', '.join(sorted(EXCLUDE_SUFFIX))}\n")
    buf.write("\n")
    buf.write("path :: lines :: mtime\n")
    buf.write("----------------------------------------\n")

    for rel, n, mt in files_info:
        buf.write(f"{rel} :: {n} :: {mt}\n")

    buf.write("----------------------------------------\n")
    buf.write(f"TOTAL files: {total_files}\n")
    buf.write(f"TOTAL lines: {total_lines}\n")

    out_path.write_text(buf.getvalue(), encoding="utf-8")
    print(f"[dump] écrit: {out_path} ({total_files} fichiers, {total_lines} lignes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())