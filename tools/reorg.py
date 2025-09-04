#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/reorg.py — Réorganisation sécurisée du dépôt Scalp.

- Crée 'poubelle/' et y déplace ce qui est clairement inutile (sauvegardes, caches, venv, pid, logs).
- Normalise quelques emplacements (docs, scripts, configs, deploy/systemd, assets/dashboard).
- Ne touche PAS au code source (api/ engine/ scalper/ services/ dash/ webviz/) pour éviter de casser les imports.
- Produit un manifeste JSON + un rapport Markdown.
- Dry-run par défaut. Utiliser --apply pour exécuter.

Usage :
    python tools/reorg.py                 # dry-run
    python tools/reorg.py --apply         # applique les changements
"""

from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
POUBELLE = ROOT / "poubelle"
REPORT = ROOT / "reorg_report.md"
MANIFEST = ROOT / "reorg_moves.json"

# Patterns sûrs à jeter
TRASH_DIRS = {
    ".ipynb_checkpoints",
    "__pycache__",
    "venv",
}
TRASH_FILES_EXT = {".pid", ".pyc", ".pyo", ".pyd", ".log", ".bak", ".old", ".tmp"}
TRASH_FILES_EXACT = {
    ".httpserver.pid",
    "resultat.log",
    ".gitconfig",
    ".gitconfig.bak",
    "dashboard.html.bak",
    "makefile",   # doublon non standard (minuscule)
}

# Normalisations (source -> destination relative)
MOVE_MAP = {
    # Dossiers
    ("workflows",): ".github/workflows",
    ("systemctl",): "deploy/systemd",
    ("bin",): "scripts",
    # Fichiers vers docs
    ("INSTALL.txt",): "docs/INSTALL.md",
    ("PROCESSUS",): "docs/PROCESSUS.md",
    ("PROMPT.md",): "docs/PROMPT.md",
    ("README - Quick start",): "docs/README-quick-start.md",
    ("STRATEGY.md",): "docs/STRATEGY.md",
    # Configs
    ("entries_config.json",): "configs/entries_config.json",
    ("backtest_config.json",): "configs/examples/backtest_config.json",
    # Assets
    ("dashboard.html",): "assets/dashboard/dashboard.html",
    # Scripts
    ("doc_build.sh",): "scripts/doc_build.sh",
    ("auto_push.sh",): "scripts/auto_push.sh",
    ("run-dash.sh",): "scripts/run-dash.sh",
    ("run-live.sh",): "scripts/run-live.sh",
}

# Éléments à ARCHIVER (poubelle/archive) car probablement obsolètes
ARCHIVE_DIRS = {"backup", "front401"}
ARCHIVE_FILES_PREFIX = {"bot.py.bak."}

# Dossiers à créer si besoin
ENSURE_DIRS = [
    "docs",
    "configs",
    "configs/examples",
    "scripts",
    "deploy/systemd",
    "assets/dashboard",
    ".github/workflows",
    "data/examples",
    "var",
    "poubelle/archive",
]

def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False

def safe_move(src: Path, dst: Path, apply: bool, moves: list[dict]):
    """Déplace src vers dst (crée dossiers), journalise l'action."""
    dst_parent = dst.parent
    if apply:
        dst_parent.mkdir(parents=True, exist_ok=True)
        # Utilise git mv si possible (pour préserver l'historique)
        if (ROOT / ".git").exists():
            try:
                import subprocess
                subprocess.run(["git", "mv", str(src), str(dst)], check=True)
            except Exception:
                shutil.move(str(src), str(dst))
        else:
            shutil.move(str(src), str(dst))
    action = {"from": str(src.relative_to(ROOT)),
              "to": str(dst.relative_to(ROOT)),
              "type": "move"}
    moves.append(action)

def move_to_trash(p: Path, apply: bool, moves: list[dict], subdir: str = ""):
    target = POUBELLE / subdir / p.name
    safe_move(p, target, apply, moves)

def should_trash_file(p: Path) -> bool:
    if p.suffix.lower() in TRASH_FILES_EXT:
        return True
    if p.name in TRASH_FILES_EXACT:
        return True
    for pref in ARCHIVE_FILES_PREFIX:
        if p.name.startswith(pref):
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Réorganisation sécurisée du dépôt Scalp")
    parser.add_argument("--apply", action="store_true", help="Appliquer réellement les déplacements")
    args = parser.parse_args()
    dry = not args.apply

    moves: list[dict] = []
    created: list[str] = []

    # Prépare les dossiers
    for d in ENSURE_DIRS:
        path = ROOT / d
        if not path.exists():
            if not dry:
                path.mkdir(parents=True, exist_ok=True)
            created.append(d)

    # Parcours racine (uniquement éléments de 1er niveau)
    for item in ROOT.iterdir():
        if item.name in {".git", "poubelle", ".github"}:
            continue

        # 1) TRASH dossiers
        if item.is_dir() and item.name in TRASH_DIRS:
            move_to_trash(item, not dry, moves)
            continue

        # 2) ARCHIVE dossiers
        if item.is_dir() and item.name in ARCHIVE_DIRS:
            move_to_trash(item, not dry, moves, subdir="archive")
            continue

        # 3) TRASH fichiers (extensions/nom)
        if item.is_file() and should_trash_file(item):
            move_to_trash(item, not dry, moves)
            continue

        # 4) Normalisations ciblées (MOVE_MAP)
        moved = False
        for src_tuple, dest_rel in MOVE_MAP.items():
            if item.name in src_tuple:
                dest = ROOT / dest_rel
                # Si INSTALL.txt -> INSTALL.md, convertir l'extension
                if item.name == "INSTALL.txt":
                    # Renommage en .md
                    dest = dest.with_suffix(".md")
                safe_move(item, dest, not dry, moves)
                moved = True
                break
        if moved:
            continue

        # 5) NE PAS toucher au code source pour l’instant
        if item.name in {"api", "engine", "scalper", "services", "dash", "webviz"}:
            continue

        # 6) Cas particuliers
        if item.name == "workflows" and item.is_dir():
            # Si non attrapé plus haut
            safe_move(item, ROOT / ".github/workflows", not dry, moves)
            continue

        if item.name == "data" and item.is_dir():
            # juste s'assurer d'un .gitkeep
            gitkeep = item / ".gitkeep"
            if not dry:
                gitkeep.touch(exist_ok=True)
            continue

        if item.name == "var" and item.is_dir():
            gitkeep = item / ".gitkeep"
            if not dry:
                gitkeep.touch(exist_ok=True)
            continue

        # 7) init.py mal nommé à la racine
        if item.is_file() and item.name == "init.py":
            dest = ROOT / "src/scalp/__init__.py"
            safe_move(item, dest, not dry, moves)
            # S'assure du dossier
            if not dry:
                (ROOT / "src/scalp").mkdir(parents=True, exist_ok=True)
            continue

    # Rapport
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "dry_run": dry,
        "moves": moves,
        "created_dirs": created,
    }
    if not dry:
        MANIFEST.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Rapport Markdown
    lines = [
        "# Rapport de réorganisation",
        f"- Date (UTC) : {summary['timestamp']}",
        f"- Dry-run : {summary['dry_run']}",
        f"- Dossiers créés : {', '.join(created) if created else '(aucun)'}",
        "",
        "## Déplacements :",
    ]
    if moves:
        for m in moves:
            lines.append(f"- `{m['from']}` → `{m['to']}`")
    else:
        lines.append("(aucun)")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Rapport écrit dans {REPORT.relative_to(ROOT)}")
    if not dry:
        print(f"[OK] Manifeste écrit dans {MANIFEST.relative_to(ROOT)}")
    else:
        print("[INFO] Dry-run : aucun fichier déplacé. Ajoutez --apply pour appliquer.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
