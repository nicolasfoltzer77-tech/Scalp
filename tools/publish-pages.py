#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publication automatique du dashboard vers GitHub Pages.
- Copie les JSON dans /docs/data
- Commit + push sur la branche configurée
"""

import os, sys, subprocess, shutil
from pathlib import Path

def main():
    repo_root = Path(__file__).resolve().parents[1]
    docs_dir  = repo_root / "docs"
    data_dir  = docs_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    reports_dir = repo_root / "scalp_data" / "reports"

    # Copier les JSON utiles
    for name in ["status.json", "summary.json", "last_errors.json"]:
        src = reports_dir / name
        dst = data_dir / name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"[publish] Copié {src.name} → {dst}")

    # Git config depuis ENV
    user   = os.environ.get("GIT_USER")
    token  = os.environ.get("GIT_TOKEN")
    repo   = os.environ.get("GIT_REPO", "Scalp")
    branch = os.environ.get("GIT_BRANCH", "main")

    if not user or not token:
        raise RuntimeError("GIT_USER / GIT_TOKEN non définis")

    repo_url = f"https://{user}:{token}@github.com/{user}/{repo}.git"

    # Git add / commit / push
    subprocess.run(["git", "config", "user.email", f"{user}@noreply.github.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", user], cwd=repo_root, check=True)

    subprocess.run(["git", "add", "docs"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "update dashboard"], cwd=repo_root, check=False)
    subprocess.run(["git", "push", repo_url, branch], cwd=repo_root, check=True)

    print("[publish] Dashboard poussé sur GitHub Pages !")


if __name__ == "__main__":
    main()