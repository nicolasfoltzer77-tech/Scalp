#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exporte les artefacts du dashboard vers /docs pour GitHub Pages.
- Copie dashboard.html (→ docs/index.html) + debug.txt/html
- Copie les JSON (summary/status/last_errors) vers docs/data/
- Option --push pour git add/commit/push (utilise GH_TOKEN si présent)
"""

from __future__ import annotations
import os, sys, shutil, json, time, subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR  = REPO_ROOT / "docs"
DATA_DIR  = Path("/notebooks/scalp_data/data")
REPORTS_DIR = Path("/notebooks/scalp_data/reports")

def info(msg): print(f"[export] {msg}")

def ensure_dirs():
    (DOCS_DIR / "data").mkdir(parents=True, exist_ok=True)

def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        info(f"copied: {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
    else:
        info(f"missing: {src}")

def write_index_redirect():
    """Si dashboard.html n'existe pas, créer une page minimale."""
    idx = DOCS_DIR / "index.html"
    if not idx.exists():
        idx.write_text("""<!doctype html><meta charset="utf-8">
<title>SCALP</title><h1>SCALP</h1>
<p>dashboard.html introuvable — lance le maintainer pour le générer.</p>
""", encoding="utf-8")

def export_docs():
    ensure_dirs()

    # 1) dashboard -> index.html (Pages sert /docs/index.html)
    dash_src = REPO_ROOT / "dashboard.html"
    dash_dst = DOCS_DIR / "index.html"
    copy_if_exists(dash_src, dash_dst)

    # 2) debug
    copy_if_exists(REPO_ROOT / "debug.txt",  DOCS_DIR / "debug.txt")
    copy_if_exists(REPO_ROOT / "debug.html", DOCS_DIR / "debug.html")

    # 3) data JSON (pour éventuelles pages JS futures)
    copy_if_exists(REPORTS_DIR / "summary.json",     DOCS_DIR / "data" / "summary.json")
    copy_if_exists(REPORTS_DIR / "status.json",      DOCS_DIR / "data" / "status.json")
    copy_if_exists(REPORTS_DIR / "last_errors.json", DOCS_DIR / "data" / "last_errors.json")

    # 4) fallback si pas de dashboard
    write_index_redirect()

def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=str(REPO_ROOT), check=check, capture_output=True, text=True)

def maybe_push(commit_msg: str):
    # Config git si besoin
    try:
        git("rev-parse", "--is-inside-work-tree")
    except subprocess.CalledProcessError:
        info("Ce dossier n'est pas un dépôt git. Skip push.")
        return

    # User/Email fallback
    try:
        git("config", "user.email")
    except subprocess.CalledProcessError:
        git("config", "user.email", "bot@local")
    try:
        git("config", "user.name")
    except subprocess.CalledProcessError:
        git("config", "user.name", "SCALP Bot")

    # Ajouter /docs
    git("add", "docs")

    # Commit si changements
    cp = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(REPO_ROOT))
    if cp.returncode == 0:
        info("Aucun changement à committer.")
        return
    git("commit", "-m", commit_msg)

    # Remote avec token si GH_TOKEN et GH_REPO fournis
    token = os.environ.get("GH_TOKEN", "").strip()
    gh_repo = os.environ.get("GH_REPO", "").strip()  # ex: "monuser/scalp"
    if token and gh_repo:
        # set remote origin si absent
        remotes = git("remote", "show").stdout.strip().splitlines()
        if "origin" not in remotes:
            url = f"https://x-access-token:{token}@github.com/{gh_repo}.git"
            git("remote", "add", "origin", url)
        else:
            # réécrit l'URL en https token si besoin
            url = f"https://x-access-token:{token}@github.com/{gh_repo}.git"
            git("remote", "set-url", "origin", url)

        # push
        try:
            git("push", "origin", "HEAD:main")
            info("Pushed to origin main.")
        except subprocess.CalledProcessError as e:
            info(f"Push failed: {e.stderr}")
    else:
        info("GH_TOKEN ou GH_REPO manquant → push ignoré.")

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="git add/commit/push après export")
    args = ap.parse_args()

    export_docs()
    if args.push:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        maybe_push(commit_msg=f"pages: update artifacts at {ts} UTC")

    print("\n[export] Done. Ouvre GitHub Pages après déploiement: https://<user>.github.io/<repo>/")

if __name__ == "__main__":
    main()