#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publication GitHub Pages SANS PROMPT.

- Copie les artefacts vers /docs :
  * HTML : docs/index.html, docs/dashboard.html (déjà écrits par render_report)
  * JSON : docs/data/{summary.json,status.json,last_errors.json}
- Commit + push via token (env: GIT_USER, GIT_TOKEN, GIT_REPO, GIT_BRANCH)
- N'échoue pas le process principal si pas de token ou si aucune modif
"""

from __future__ import annotations
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

# Empêcher toute invite interactive
os.environ["GIT_TERMINAL_PROMPT"] = "0"

# ----- Helpers -----
def sh(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    print("[sh]", " ".join(args))
    return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=check)

def time_utc() -> str:
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

# ----- Main -----
def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]   # <repo>
    docs_dir  = repo_root / "docs"
    data_dir  = docs_dir / "data"
    docs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1) Copier les JSON depuis reports -> docs/data
    #    (plusieurs emplacements possibles suivant ta config)
    reports_candidates = [
        Path("/notebooks/scalp_data/reports"),
        repo_root / "scalp_data" / "reports",
    ]
    reports_dir = next((p for p in reports_candidates if p.exists()), None)

    if reports_dir:
        for name in ("summary.json", "status.json", "last_errors.json"):
            src = reports_dir / name
            dst = data_dir / name
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"[publish] Copié {src} -> {dst}")
            else:
                print(f"[publish] Manquant (ok): {src}")
    else:
        print("[publish] Aucun reports_dir trouvé, skip copie JSON.")

    # 2) Préparer Git (si token dispo)
    user   = os.environ.get("GIT_USER", "").strip()
    token  = os.environ.get("GIT_TOKEN", "").strip()
    repo   = os.environ.get("GIT_REPO", "Scalp").strip()
    branch = os.environ.get("GIT_BRANCH", "main").strip()

    if not user or not token:
        print("[publish] GIT_USER/GIT_TOKEN absents -> push ignoré (écriture locale OK).")
        return

    origin_url = f"https://x-access-token:{token}@github.com/{user}/{repo}.git"

    # 3) Config identité Git + origin
    try:
        try:
            sh(["git", "config", "user.email"], repo_root, check=True)
        except subprocess.CalledProcessError:
            sh(["git", "config", "user.email", f"{user}@users.noreply.github.com"], repo_root, check=True)
        try:
            sh(["git", "config", "user.name"], repo_root, check=True)
        except subprocess.CalledProcessError:
            sh(["git", "config", "user.name", user], repo_root, check=True)

        rem = sh(["git", "remote"], repo_root, check=False)
        remotes = (rem.stdout or "").split()
        if "origin" in remotes:
            sh(["git", "remote", "set-url", "origin", origin_url], repo_root, check=True)
        else:
            sh(["git", "remote", "add", "origin", origin_url], repo_root, check=True)
        print("[publish] origin configuré (token).")
    except subprocess.CalledProcessError as e:
        print("[publish] ⚠️ configuration git/remote échouée:", (e.stdout or e.stderr).strip())
        return

    # 4) Stage /docs (HTML + JSON)
    try:
        sh(["git", "add", "docs"], repo_root, check=True)
    except subprocess.CalledProcessError as e:
        print("[publish] ⚠️ git add docs échoué:", (e.stdout or e.stderr).strip())
        return

    # 5) Commit uniquement s'il y a des changements
    diff_rc = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(repo_root)).returncode
    if diff_rc == 0:
        print("[publish] Aucun changement à committer.")
        return

    try:
        sh(["git", "commit", "-m", f"pages: update at {time_utc()}"], repo_root, check=True)
    except subprocess.CalledProcessError as e:
        print("[publish] ⚠️ git commit échoué:", (e.stdout or e.stderr).strip())
        return

    # 6) Push
    try:
        sh(["git", "push", "origin", f"HEAD:{branch}"], repo_root, check=True)
        print("[publish] ✅ Push OK.")
    except subprocess.CalledProcessError as e:
        print("[publish] ❌ Push KO:", (e.stdout or e.stderr).strip())

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[publish] FATAL: {exc}")
        sys.exit(1)