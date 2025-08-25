#!/usr/bin/env python3
# tools/trashify.py
"""
Ménage du dépôt : déplace les éléments legacy/ inutiles vers .trash/<TIMESTAMP>/
- DRY RUN par défaut (aucune action tant que --apply n'est pas passé)
- Liste adaptée au dump le plus récent
- Prend soin de garder le dernier dump dans dumps/
- Sécurisé : ne touche jamais .git/ ni .trash/

Usage :
  python tools/trashify.py                 # aperçu (DRY RUN)
  python tools/trashify.py --apply         # exécute les déplacements
  python tools/trashify.py --restore PATH  # restaure depuis .trash/
  python tools/trashify.py --aggressive    # inclut fichiers/dev en plus (toujours DRY tant que --apply pas présent)
"""

from __future__ import annotations
import argparse
import os
import shutil
import time
from pathlib import Path
from typing import Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]


# --- Cibles principales (safe) ------------------------------------------------
TRASH_DIRS_SAFE = [
    "scalper",                 # ancien moteur non utilisé par bot.py
    "tests",                   # dossiers de tests obsolètes
    "data",                    # les données doivent être hors dépôt
]

TRASH_GLOBS_COMMON = [
    "**/__pycache__",          # caches py
    "**/.ipynb_checkpoints",   # artefacts jupyter
]

TRASH_FILES_SAFE = [
    "engine/core/signal.py",   # doublon vs signals.py
    "dump.txt",                # vieux dump
    "requirements-dash.txt",   # on garde un seul requirements.txt
    "requirements-dev.txt",
]

# --- Cibles 'agressives' optionnelles ----------------------------------------
TRASH_FILES_AGGRESSIVE = [
    "pytest.ini",
    ".pytest_cache",
]


# --- Helpers ------------------------------------------------------------------
def _existing(paths: Iterable[Path]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        try:
            if p.exists():
                out.append(p)
        except OSError:
            pass
    return out

def _is_protected(p: Path) -> bool:
    rp = p.resolve()
    # ne jamais toucher au repo root lui‑même, ni .git, ni .trash
    for forbid in [REPO_ROOT, REPO_ROOT / ".git", REPO_ROOT / ".trash"]:
        try:
            if rp == forbid.resolve() or str(rp).startswith(str(forbid.resolve())):
                return True
        except Exception:
            continue
    return False

def _collect_basic_targets(aggressive: bool) -> List[Path]:
    items: List[Path] = []

    # dossiers exacts
    items += _existing([REPO_ROOT / d for d in TRASH_DIRS_SAFE])

    # fichiers exacts
    base_files = TRASH_FILES_SAFE + (TRASH_FILES_AGGRESSIVE if aggressive else [])
    items += _existing([REPO_ROOT / f for f in base_files])

    # globs
    for pat in TRASH_GLOBS_COMMON:
        for p in REPO_ROOT.glob(pat):
            items.append(p)

    # filtre de sécurité
    safe = [p for p in items if not _is_protected(p)]
    # dédupliquer et trier (dossiers parents avant enfants)
    safe_sorted = sorted(set(safe), key=lambda x: (str(x).count(os.sep), str(x)))
    return safe_sorted

def _collect_old_dumps() -> List[Path]:
    """Dans dumps/, garder le fichier le plus récent et déplacer les autres."""
    d = REPO_ROOT / "dumps"
    if not d.exists() or not d.is_dir():
        return []
    files = sorted([p for p in d.glob("DUMP_*.txt") if p.is_file()],
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if len(files) <= 1:
        return []
    # on garde files[0] (le plus récent), on déplace le reste
    return files[1:]

def _move_to_trash(paths: List[Path], apply: bool, label: str = "") -> None:
    if not paths:
        return
    dest_root = REPO_ROOT / ".trash" / time.strftime("%Y%m%d-%H%M%S")
    print(f"Destination: {dest_root} {label}".rstrip())
    for p in paths:
        rel = p.relative_to(REPO_ROOT)
        dest = dest_root / rel
        print(f"- {rel}  ->  .trash/{dest.relative_to(REPO_ROOT / '.trash')}")
        if apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(p), str(dest))
            except Exception as e:
                print(f"  [!] move failed: {e}")

def _restore_from_trash(src: Path) -> None:
    src = src.resolve()
    if (REPO_ROOT / ".trash") not in src.parents:
        raise SystemExit("Le chemin à restaurer doit provenir de .trash/")
    rel = src.relative_to(REPO_ROOT / ".trash")
    dest = REPO_ROOT / rel
    print(f"RESTORE  .trash/{rel} -> {rel}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))


# --- Main ---------------------------------------------------------------------
def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Exécuter réellement (sinon DRY RUN).")
    ap.add_argument("--restore", type=str, default="", help="Chemin à restaurer depuis .trash/")
    ap.add_argument("--aggressive", action="store_true", help="Inclut aussi fichiers/dev optionnels (pytest.ini, etc.).")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.restore:
        _restore_from_trash(Path(args.restore))
        return 0

    print(f"[trashify] Repo : {REPO_ROOT}")
    basic = _collect_basic_targets(args.aggressive)
    print(f"[trashify] Cibles de base détectées : {len(basic)}")
    _move_to_trash(basic, apply=args.apply)

    # dumps obsolètes (garde le plus récent)
    old_dumps = _collect_old_dumps()
    if old_dumps:
        print(f"[trashify] Dumps obsolètes : {len(old_dumps)} (le plus récent est conservé)")
        _move_to_trash(old_dumps, apply=args.apply, label="(dumps)")

    if not args.apply:
        print("\nDRY RUN — ajoute --apply pour déplacer réellement.")
    else:
        print("\n[✓] Déplacement terminé. Vérifie .trash/, puis commit/push si ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())