# tools/trashify.py
# Déplacement sécurisé des fichiers/dossiers "candidats" vers TRASH_YYYYMMDD-HHMMSS/
# Usage:
#   python tools/trashify.py            # dry-run (affiche seulement)
#   python tools/trashify.py --apply    # déplace réellement
# Options:
#   --trash-dir NAME   # nom personnalisé du dossier trash (sinon timestamp)
#   --no-git           # force l'utilisation de shutil.move au lieu de `git mv`
#
# Notes:
# - Détecte automatiquement un repo Git et utilise `git mv` si possible (meilleure traçabilité).
# - Écrit un manifeste: TRASH_.../TRASH_MANIFEST.txt avec la liste des éléments déplacés.
# - La liste des "candidats" ci-dessous est issue du dump fourni le 2025-08-24 (répertoire racine: Scalp/).  #  [oai_citation:1‡Vierge 19.txt](file-service://file-9QiWVhpqthb1XibRXMXmiu)

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

# --------------------------------------------------------------------------------------
# Candidats à déplacer (conservateur). Ajuste cette liste si besoin avant --apply.
# --------------------------------------------------------------------------------------
CANDIDATES: List[str] = [
    # 1) Ancienne corbeille entière (archives obsolètes) — doublons du code actuel
    "TRASH_20250823-124533",

    # 2) Duplication manifeste: indicateurs déjà présents sous scalper/core/indicators.py
    "data/indicators.py",

    # 3) Typo de dossier de stratégie (probablement un essai non concluant)
    "scalper/strategy/startegies",  # <- oui "startegies" (typo)

    # 4) Scripts ponctuels/démo non utilisés par bot.py
    # (laisse commentés par défaut; décommente si tu valides)
    # "tg_diag.py",
    # "TRASH_20250823-124533/quick_order.py",
    # "TRASH_20250823-124533/dashboard.py",
    # "TRASH_20250823-124533/notebooks",

    # 5) Anciennes configs/legacy dans TRASH (redondantes avec scalper/config/* actuels)
    # (déjà couvert par la ligne 1 déplaçant le dossier complet)
]

# Racine du repo = dossier parent de CE fichier, puis deux niveaux si placé dans tools/
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parent.parent if HERE.parent.name == "tools" else HERE.parent
assert (REPO_ROOT / ".").exists(), f"Repo root introuvable: {REPO_ROOT}"


def _is_git_repo(root: Path) -> bool:
    return (root / ".git").exists()


def _git_mv(src: Path, dst: Path) -> Tuple[bool, str]:
    try:
        subprocess.run(["git", "mv", str(src), str(dst)], cwd=REPO_ROOT, check=True, capture_output=True)
        return True, "git mv"
    except Exception as e:
        return False, f"git mv failed: {e}"


def _shutil_mv(src: Path, dst: Path) -> Tuple[bool, str]:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True, "shutil.move"
    except Exception as e:
        return False, f"move failed: {e}"


def _timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def resolve_existing(paths: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for p in paths:
        rp = (REPO_ROOT / p).resolve()
        if rp.exists():
            out.append(rp)
    return out


def write_manifest(trash_dir: Path, moved: List[Path], skipped: List[Tuple[Path, str]]) -> None:
    manifest = trash_dir / "TRASH_MANIFEST.txt"
    lines: List[str] = []
    lines.append(f"Repo root: {REPO_ROOT}")
    lines.append(f"Trash dir: {trash_dir}")
    lines.append(f"Moved count: {len(moved)}")
    lines.append("Moved items:")
    for p in moved:
        rel = p.relative_to(trash_dir)
        lines.append(f"  - {rel}")
    if skipped:
        lines.append("")
        lines.append("Skipped/not moved (reason):")
        for p, reason in skipped:
            lines.append(f"  - {p.relative_to(REPO_ROOT)} :: {reason}")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Déplacer des fichiers/dossiers vers un répertoire TRASH_*")
    ap.add_argument("--apply", action="store_true", help="Exécuter réellement les déplacements (sinon dry-run)")
    ap.add_argument("--trash-dir", default="", help="Nom personnalisé du répertoire trash (par défaut TRASH_<timestamp>)")
    ap.add_argument("--no-git", action="store_true", help="Ne pas utiliser git mv, forcer shutil.move")
    args = ap.parse_args()

    # Résolution des candidats présents
    existing = resolve_existing(CANDIDATES)
    missing = sorted(set(CANDIDATES) - {str(p.relative_to(REPO_ROOT)) for p in existing})
    if missing:
        print("[i] Éléments non trouvés (ignorés) :")
        for m in missing:
            print(f"    - {m}")

    if not existing:
        print("[✓] Rien à déplacer: aucun candidat présent.")
        return 0

    # Dossier TRASH cible
    trash_name = args.trash_dir.strip() or f"TRASH_{_timestamp()}"
    trash_dir = (REPO_ROOT / trash_name).resolve()

    print(f"[i] Repo: {REPO_ROOT}")
    print(f"[i] Trash: {trash_dir}")
    print("[i] Candidats résolus:")
    for p in existing:
        print(f"    - {p.relative_to(REPO_ROOT)}")

    if not args.apply:
        print("\n[DRY-RUN] Ajoute --apply pour exécuter réellement les déplacements.")
        return 0

    # Exécution
    moved: List[Path] = []
    skipped: List[Tuple[Path, str]] = []
    use_git = _is_git_repo(REPO_ROOT) and not args.no_git

    for src in existing:
        rel = src.relative_to(REPO_ROOT)
        dst = trash_dir / rel  # conserve la structure relative
        dst.parent.mkdir(parents=True, exist_ok=True)

        if use_git:
            ok, how = _git_mv(src, dst)
        else:
            ok, how = _shutil_mv(src, dst)

        if ok:
            print(f"[→] {rel}  ->  {dst.relative_to(REPO_ROOT)}  ({how})")
            moved.append(dst)
        else:
            print(f"[!] SKIP {rel} ({how})")
            skipped.append((src, how))

    # Manifeste
    write_manifest(trash_dir, moved, skipped)
    print(f"[✓] Manifeste écrit: {trash_dir / 'TRASH_MANIFEST.txt'}")
    print("[✓] Terminé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())