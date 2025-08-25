# ops/migrate_to_engine.py
from __future__ import annotations
import re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine"
ENGINE.mkdir(exist_ok=True)

# 1) Déplacer anciens packages s'ils existent
CANDIDATE_PKGS = ["scalper", "scalp"]  # anciens noms possibles de package interne
for name in CANDIDATE_PKGS:
    src = ROOT / name
    if src.exists() and src.is_dir():
        dst = ENGINE
        # on déplace le contenu interne dans engine/
        for p in src.iterdir():
            dest = dst / p.name
            if dest.exists():
                continue
            shutil.move(str(p), str(dest))
        # on laisse le répertoire racine (vide) à supprimer manuellement si besoin

# 2) Mettre à jour les imports dans tout le repo (hors TRASH et .git)
PATTERNS = [
    (re.compile(r"\bscalper\."), "engine."),
    (re.compile(r"\bscalp\."), "engine."),   # ancien package interne homonyme du repo
]
def fix_file(path: Path) -> None:
    try:
        txt = path.read_text(encoding="utf-8")
    except Exception:
        return
    orig = txt
    for rx, repl in PATTERNS:
        txt = rx.sub(repl, txt)
    if txt != orig:
        path.write_text(txt, encoding="utf-8")

for p in ROOT.rglob("*.py"):
    rel = p.relative_to(ROOT)
    if any(part.startswith("TRASH_") for part in rel.parts):
        continue
    if rel.parts and rel.parts[0] in (".git",):
        continue
    fix_file(p)

print("[✓] Migration terminée. Vérifie les imports et supprime l’ancien dossier vide si présent.")