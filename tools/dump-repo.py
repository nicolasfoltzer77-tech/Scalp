#!/usr/bin/env python3
# scalp/tools/dump-repo.py
# -------------------------------------------------------------------
# Dump simple de /notebooks/scalp :
#   - exclut dossiers/fichiers inutiles (tests, backtest, csv, images…)
#   - inclut le code complet des fichiers restants
#   - ajoute nb lignes + date modif
#   - écrit dans notebooks/scalp/dumps/DUMP_YYYYMMDD-HHMMSS.txt
# -------------------------------------------------------------------

from __future__ import annotations
import sys, io, time
from pathlib import Path
from datetime import datetime

ROOT = Path("/notebooks/scalp")
OUT_DIR = ROOT / "dumps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Extensions considérées comme texte utile
ALLOW_EXT = {".py", ".yml", ".yaml", ".sh", ".txt", ".md", ".ini", ".cfg"}

# Dossiers exclus
EXCLUDE_DIRS = {
    ".git", ".github", ".idea", ".vscode",
    ".ipynb_checkpoints", "__pycache__", ".mypy_cache", ".pytest_cache",
    "backups", "dumps", "dump", "build", "dist",
    "dash", "tests", "scalp0", "scalp1", "scalp2", "scalp3",
    "engine/backtest",
}

# Suffixes exclus (binaires / data lourdes)
EXCLUDE_SUFFIX = {
    ".csv", ".parquet", ".feather", ".log",
    ".gz", ".zip", ".xz", ".bz2",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf",
    ".ipynb",
}

def is_excluded(path: Path) -> bool:
    parts = path.relative_to(ROOT).parts
    if len(parts) >= 2 and f"{parts[0]}/{parts[1]}" in EXCLUDE_DIRS:
        return True
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    if path.suffix.lower() in EXCLUDE_SUFFIX:
        return True
    return False

def fmt_mtime(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "1970-01-01 00:00:00"

def main() -> int:
    if not ROOT.exists():
        print(f"[!] Dossier introuvable : {ROOT}", file=sys.stderr)
        return 2

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
        try:
            code = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            code = ""
        nlines = code.count("\n") + 1 if code else 0
        mtime = fmt_mtime(p.stat().st_mtime)
        files_info.append((str(rel), nlines, mtime, code))

    files_info.sort()

    buf = io.StringIO()
    buf.write("# ---- DUMP SCALP ----\n")
    buf.write(f"time   : {fmt_mtime(time.time())}\n")
    buf.write(f"root   : {ROOT}\n")
    buf.write(f"output : {out_path}\n\n")

    total_lines = 0
    for rel, n, mt, code in files_info:
        total_lines += n
        buf.write(f"\n# ===== {rel} ===== ({n} lignes, modifié {mt})\n\n")
        buf.write(code)
        if not code.endswith("\n"):
            buf.write("\n")

    buf.write(f"\n# ---- Résumé ----\n")
    buf.write(f"Fichiers : {len(files_info)}\n")
    buf.write(f"Lignes   : {total_lines}\n")

    out_path.write_text(buf.getvalue(), encoding="utf-8")
    print(f"[dump] écrit: {out_path} ({len(files_info)} fichiers, {total_lines} lignes)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())