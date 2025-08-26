#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publie le dashboard et les données vers GitHub Pages (/docs) SANS PROMPT.
- Copie/assure : docs/index.html, docs/dashboard.html
- Copie : reports JSON -> docs/data/ (summary, status, last_errors)
- Force le remote 'origin' avec token (GIT_USER/GIT_TOKEN/GIT_REPO)
- git add/commit/push sur GIT_BRANCH (défaut: main)
"""

from __future__ import annotations
import os, sys, shutil, subprocess
from pathlib import Path
from typing import Iterable

# ---- Vars d'env attendues (déjà présentes chez toi) ----
GIT_USER   = os.environ.get("GIT_USER", "").strip()
GIT_TOKEN  = os.environ.get("GIT_TOKEN", "").strip()
GIT_REPO   = os.environ.get("GIT_REPO", "Scalp").strip()   # nom du repo
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main").strip()

# Fallback compatibles si tu utilises GH_* ailleurs
if not GIT_USER and os.environ.get("GH_USER"):   GIT_USER   = os.environ["GH_USER"].strip()
if not GIT_TOKEN and os.environ.get("GH_TOKEN"): GIT_TOKEN  = os.environ["GH_TOKEN"].strip()
if not GIT_REPO and os.environ.get("GH_REPO"):
    # "user/repo" -> on prendra le repo seulement
    GIT_REPO = os.environ["GH_REPO"].split("/")[-1].strip()

REPO_PATH  = Path(os.environ.get("REPO_PATH", "/notebooks/scalp"))
REPO_ROOT  = REPO_PATH
DOCS_DIR   = REPO_ROOT / "docs"
DATA_DIR   = Path("/notebooks/scalp_data/data")            # pas nécessairement poussé
REPORTS_DIR= Path("/notebooks/scalp_data/reports")         # JSON à publier

# Empêche tout prompt interactif de git
os.environ["GIT_TERMINAL_PROMPT"] = "0"

def sh(cmd: list[str]|str, cwd: Path|None=None, check=True) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        shell=True; args=cmd
    else:
        shell=False; args=cmd
    print(f"[sh] {cmd}")
    return subprocess.run(args, cwd=str(cwd) if cwd else None,
                          text=True, capture_output=True, shell=shell, check=check)

def ensure_docs():
    (DOCS_DIR / "data").mkdir(parents=True, exist_ok=True)

def copy(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"[copy] {src} -> {dst}")
    else:
        print(f"[skip] missing: {src}")

def export_artifacts():
    ensure_docs()

    # 1) dashboard généré par tools/render_report.py (il peut être à la racine ou déjà dans docs)
    dash_candidates = [
        REPO_ROOT / "dashboard.html",
        DOCS_DIR / "dashboard.html",
        DOCS_DIR / "index.html"
    ]
    dash = next((p for p in dash_candidates if p.exists()), None)

    if dash is None:
        # fallback minimal si aucun dashboard présent
        idx = DOCS_DIR / "index.html"
        idx.write_text("<h1>SCALP</h1><p>Dashboard non généré.</p>", encoding="utf-8")
        print("[warn] Aucun dashboard trouvé, index minimal généré.")
    else:
        # on garantit index.html + dashboard.html
        copy(dash, DOCS_DIR / "index.html")
        copy(dash, DOCS_DIR / "dashboard.html")

    # 2) JSON
    copy(REPORTS_DIR / "summary.json",     DOCS_DIR / "data" / "summary.json")
    copy(REPORTS_DIR / "status.json",      DOCS_DIR / "data" / "status.json")
    copy(REPORTS_DIR / "last_errors.json", DOCS_DIR / "data" / "last_errors.json")

def ensure_git_identity():
    try:
        sh(["git","config","user.email"], cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError:
        sh(["git","config","user.email","bot@scalp.local"], cwd=REPO_ROOT, check=True)
    try:
        sh(["git","config","user.name"], cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError:
        sh(["git","config","user.name","SCALP Bot"], cwd=REPO_ROOT, check=True)

def set_remote_with_token():
    """
    Force origin à https://x-access-token:<token>@github.com/<user>/<repo>.git
    -> aucun prompt 'Username for https://github.com:'.
    """
    assert GIT_USER and GIT_TOKEN and GIT_REPO, "Variables GIT_USER/GIT_TOKEN/GIT_REPO manquantes"
    url = f"https://x-access-token:{GIT_TOKEN}@github.com/{GIT_USER}/{GIT_REPO}.git"
    try:
        rem = sh(["git","remote"], cwd=REPO_ROOT, check=False)
        remotes = (rem.stdout or "").split()
        if "origin" in remotes:
            sh(["git","remote","set-url","origin", url], cwd=REPO_ROOT, check=True)
        else:
            sh(["git","remote","add","origin", url], cwd=REPO_ROOT, check=True)
        print(f"[git] origin -> {url.replace(GIT_TOKEN,'***')}")
    except subprocess.CalledProcessError as e:
        print(e.stdout or e.stderr)
        raise

def git_add_commit(paths: Iterable[Path]):
    # stage
    for p in paths:
        rel = p.relative_to(REPO_ROOT)
        sh(["git","add", str(rel)], cwd=REPO_ROOT, check=True)

    # commit only if changes
    diff = subprocess.run(["git","diff","--cached","--quiet"], cwd=str(REPO_ROOT))
    if diff.returncode == 0:
        print("[git] Aucun changement à committer.")
        return False

    msg = f"pages: update {os.environ.get('PAPERSPACE_NOTEBOOK_ID','')} at {os.popen('date -u +%F_%T').read().strip()}Z"
    sh(["git","commit","-m", msg], cwd=REPO_ROOT, check=True)
    print("[git] commit ok")
    return True

def git_push():
    try:
        sh(["git","push","origin", f"HEAD:{GIT_BRANCH}"], cwd=REPO_ROOT, check=True)
        print("[git] ✅ push ok")
    except subprocess.CalledProcessError as e:
        print("[git] ❌ push failed")
        print(e.stdout or e.stderr)
        sys.exit(1)

def main():
    # Vérifier repo
    try:
        sh(["git","rev-parse","--is-inside-work-tree"], cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError:
        print(f"[fatal] {REPO_ROOT} n'est pas un dépôt git")
        sys.exit(1)

    export_artifacts()
    ensure_git_identity()
    set_remote_with_token()

    # Prépare la liste des chemins à pousser
    paths = [
        DOCS_DIR / "index.html",
        DOCS_DIR / "dashboard.html",
        DOCS_DIR / "data" / "summary.json",
        DOCS_DIR / "data" / "status.json",
        DOCS_DIR / "data" / "last_errors.json",
    ]

    changed = git_add_commit(paths)
    if changed:
        git_push()
    else:
        print("[git] Rien à pousser.")

if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"[fatal] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[fatal] {e}")
        sys.exit(1)