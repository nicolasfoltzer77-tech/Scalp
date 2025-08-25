#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DUMP_DIR = REPO_ROOT / "dumps"; DUMP_DIR.mkdir(parents=True, exist_ok=True)
TS = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_PATH = DUMP_DIR / f"DUMP_{TS}.txt"

IGNORE_EXT = {".png",".jpg",".jpeg",".gif",".pdf",".pkl",".db",".sqlite",".zip",".tar",".gz",".pyc",".pyo"}
IGNORE_DIRS = {".git","__pycache__", ".ipynb_checkpoints", "dumps"}
IGNORE_PREFIX = {"TRASH_"}

def is_text_file(p: Path) -> bool:
    if p.suffix.lower() in IGNORE_EXT: return False
    try:
        with p.open("rb") as f:
            if b"\x00" in f.read(1024): return False
        return True
    except Exception: return False

def write_header(f, t): f.write("\n"+"="*80+"\n"+t+"\n"+"="*80+"\n")

def dump_tree(root: Path, f):
    write_header(f,"ARBORESCENCE")
    for p in sorted(root.rglob("*")):
        rel=p.relative_to(root)
        if any(part in IGNORE_DIRS for part in rel.parts): continue
        if any(str(rel).startswith(pref) for pref in IGNORE_PREFIX): continue
        if p.is_file():
            m=dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{rel}  (last modified: {m})\n")
        else:
            f.write(str(rel)+"/\n")

def dump_files(root: Path, f):
    write_header(f,"FICHIERS COMPLETS")
    for p in sorted(root.rglob("*")):
        rel=p.relative_to(root)
        if p.is_dir(): continue
        if any(part in IGNORE_DIRS for part in rel.parts): continue
        if any(str(rel).startswith(pref) for pref in IGNORE_PREFIX): continue
        if not is_text_file(p): continue
        try: lines=p.read_text(encoding="utf-8",errors="replace").splitlines()
        except Exception as e:
            f.write(f"\n[!!] Impossible de lire {rel}: {e}\n"); continue
        m=dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        f.write("\n"+"-"*80+"\n"); f.write(f"FILE: {rel}  (last modified: {m})\n"); f.write("-"*80+"\n")
        for i, line in enumerate(lines, 1): f.write(f"{i:6d}: {line}\n")

def prune_old_dumps():
    for old in sorted(DUMP_DIR.glob("DUMP_*.txt")):
        if old != OUT_PATH:
            try: old.unlink(); print(f"[x] Ancien dump supprimé: {old.name}")
            except Exception as e: print(f"[!] Suppression échouée {old}: {e}")

def main() -> int:
    with OUT_PATH.open("w", encoding="utf-8") as f:
        f.write(f"# DUMP {TS}\nRepo: {REPO_ROOT}\n")
        dump_tree(REPO_ROOT, f); dump_files(REPO_ROOT, f)
    prune_old_dumps(); print(f"[✓] Dump écrit: {OUT_PATH}"); return 0

if __name__ == "__main__": sys.exit(main())