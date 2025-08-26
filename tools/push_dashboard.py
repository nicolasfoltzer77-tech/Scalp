#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Push automatique du dashboard HTML généré vers GitHub Pages (/docs/).
Utilise les variables d'environnement définies dans Paperspace.
"""

import os
import subprocess
import sys
from pathlib import Path

def run(cmd, cwd=None):
    print(f"[GIT] {cmd}")
    result = subprocess.run(cmd, cwd=cwd, shell=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(result.stdout)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main():
    # Récupère les variables d’env
    git_user   = os.environ.get("GIT_USER")
    git_token  = os.environ.get("GIT_TOKEN")
    git_repo   = os.environ.get("GIT_REPO", "Scalp")
    git_branch = os.environ.get("GIT_BRANCH", "main")
    repo_path  = os.environ.get("REPO_PATH", "/notebooks/scalp")

    if not all([git_user, git_token, git_repo]):
        print("[ERROR] Variables GIT_* manquantes")
        sys.exit(1)

    # Fichier dashboard généré
    docs_dir = Path(repo_path) / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    dashboard = docs_dir / "dashboard.html"

    if not dashboard.exists():
        print(f"[ERROR] Fichier introuvable: {dashboard}")
        sys.exit(1)

    # Remote avec token (authentification automatique)
    remote_url = f"https://{git_user}:{git_token}@github.com/{git_user}/{git_repo}.git"

    # Git push
    run("git config user.name 'AutoBot'", cwd=repo_path)
    run("git config user.email 'bot@scalp.local'", cwd=repo_path)
    run("git add docs/dashboard.html", cwd=repo_path)
    run("git commit -m 'Auto-update dashboard [skip ci]' || echo 'No changes'", cwd=repo_path)
    run(f"git push {remote_url} {git_branch}", cwd=repo_path)

    print("[OK] Dashboard poussé sur GitHub")

if __name__ == "__main__":
    main()