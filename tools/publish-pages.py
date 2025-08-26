#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publication GitHub Pages SANS PROMPT.
- Copie JSON (summary/status/last_errors) vers docs/data/
- git add/commit/push via token (GIT_USER/GIT_TOKEN/GIT_REPO/GIT_BRANCH)
"""

from __future__ import annotations
import os, sys, shutil, subprocess
from pathlib import Path

# Empêcher git de demander un username/password
os.environ["GIT_TERMINAL_PROMPT"] = "0"

def sh(args, cwd: Path, check=True):
    print("[sh]", " ".join(args))
    return subprocess.run(args, cwd=str(cwd), text=True,
                          capture_output=True, check=check)

def main():
    repo_root = Path(__file__).resolve().parents[1]
    docs_dir  = repo_root / "docs"
    data_dir  = docs_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # JSON à publier (pour consommation éventuelle côté Pages)
    # NOTE: si tes reports sont ailleurs, ajuste le chemin ici.
    reports_dir_candidates = [
        Path("/notebooks/scalp_data/reports"),
        repo_root / "scalp_data" / "reports"
    ]
    reports_dir = next((p for p in reports_dir_candidates if p.exists()), None)

    if reports_dir:
        for name in ["summary.json", "status.json", "last_errors.json"]:
            src = reports_dir / name
            dst = data_dir / name
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"[publish] Copié {src} → {dst}")
            else:
                print(f"[publish] Manquant (ok): {src}")
    else:
        print("[publish] Aucun reports_dir trouvé, skip copie JSON.")

    # Variables d’environnement pour push
    user   = os.environ.get("GIT_USER", "").strip()
    token  = os.environ.get("GIT_TOKEN", "").strip()
    repo   = os.environ.get("GIT_REPO", "Scalp").strip()
    branch = os.environ.get("GIT_BRANCH", "main").strip()

    if not user or not token:
        print("[publish] GIT_USER/GIT_TOKEN manquants → push ignoré.")
        return

    origin_url = f"https://x-access-token:{token}@github.com/{user}/{repo}.git"

    # Config identité
    try:
        sh(["git","config","user.email"], repo_root, check=True)
    except subprocess.CalledProcessError:
        sh(["git","config","user.email", f"{user}@users.noreply.github.com"], repo_root, check=True)
    try:
        sh(["git","config","user.name"], repo_root, check=True)
    except subprocess.CalledProcessError:
        sh(["git","config","user.name", user], repo_root, check=True)

    # Forcer origin avec token (pas de prompt)
    try:
        rem = sh(["git","remote"], repo_root, check=False)
        remotes = (rem.stdout or "").split()
        if "origin" in remotes:
            sh(["git","remote","set-url","origin", origin_url], repo_root, check=True)
        else:
            sh(["git","remote","add","origin", origin_url], repo_root, check=True)
        print("[publish] origin configuré (token).")
    except subprocess.CalledProcessError as e:
        print("[publish] remote config erreur:", e.stdout or e.stderr)

    # Stage /docs
    sh(["git","add","docs"], repo_root, check=True)

    # Commit si changements
    diff = subprocess.run(["git","diff","--cached","--quiet"], cwd=str(repo_root))
    if diff.returncode == 0:
        print("[publish] Aucun changement à committer.")
        return
    sh(["git","commit","-m",f"pages: update at {time_utc()}"], repo_root, check=True)

    # Push
    try:
        sh(["git","push","origin", f"HEAD:{branch}"], repo_root, check=True)
        print("[publish] ✅ Push OK.")
    except subprocess.CalledProcessError as e:
        print("[publish] ❌ Push KO:", e.stdout or e.stderr)

def time_utc():
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

if __name__ == "__main__":
    main()