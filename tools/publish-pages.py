#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publie le dashboard statique dans /docs pour GitHub Pages.

Fait :
- copie reports/*.json -> docs/data/
- écrit docs/health.json (commit, horodatage, statut)
- git add/commit/push sur la branche configurée

Config attendue (variables d'env) :
  GIT_USER      : ex. "nicolasfoltzer77-tech"
  GIT_EMAIL     : ex. "you@example.com" (optionnel)
  GIT_TOKEN     : PAT GitHub (scope repo)
  GIT_REPO      : nom du repo (ex. "scalp")
  GIT_BRANCH    : "main" (par défaut)
Optionnel :
  PAGES_URL_OUT : chemin fichier où écrire l'URL finale (ex. docs/pages_url.txt)

Hypothèses :
- On exécute ce script à la racine du repo (cwd=<repo>)
- Git origin est GitHub
- Pages est configuré sur Branch: main, Folder: /docs
"""

from __future__ import annotations
import json, os, subprocess, sys, time, shutil
from pathlib import Path

REPO_ROOT   = Path.cwd()
REPORTS_DIR = REPO_ROOT / "reports"            # <- tes jobs écrivent ici
DOCS_DIR    = REPO_ROOT / "docs"
DATA_DIR    = DOCS_DIR / "data"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

GIT_USER   = os.environ.get("GIT_USER", "").strip()
GIT_EMAIL  = os.environ.get("GIT_EMAIL", f"{GIT_USER}@users.noreply.github.com")
GIT_TOKEN  = os.environ.get("GIT_TOKEN", "").strip()
GIT_REPO   = os.environ.get("GIT_REPO", REPO_ROOT.name).strip()
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main").strip()
PAGES_URL_OUT = os.environ.get("PAGES_URL_OUT", str(DOCS_DIR / "pages_url.txt"))

def sh(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(args, cwd=str(cwd) if cwd else None,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, check=check)
    return res.stdout.strip()

def git_config():
    if GIT_USER:
        sh(["git", "config", "user.name", GIT_USER], cwd=REPO_ROOT)
    if GIT_EMAIL:
        sh(["git", "config", "user.email", GIT_EMAIL], cwd=REPO_ROOT)

def git_remote_with_token():
    # récupère l'URL origin et injecte le token si besoin
    try:
        url = sh(["git", "remote", "get-url", "origin"], cwd=REPO_ROOT)
    except Exception as e:
        print(f"[publish] pas d'origin git ? {e}")
        return
    if "github.com" not in url:
        print(f"[publish] origin n'est pas GitHub: {url}")
        return
    if GIT_TOKEN and "@" not in url:
        # https://<token>@github.com/user/repo.git
        if url.startswith("https://"):
            url = url.replace("https://", f"https://{GIT_TOKEN}@", 1)
            sh(["git", "remote", "set-url", "origin", url], cwd=REPO_ROOT)
            print("[publish] remote origin mis à jour (token)")
        else:
            print("[publish] URL origin non-https, je ne touche pas:", url)

def copy_reports():
    # Fichiers possibles côté pipeline
    candidates = [
        "status.json", "summary.json", "last_errors.json",
        "strategies.yml.next", "strategies.yml",   # si tu veux les exposer
    ]
    copied = []
    for name in candidates:
        src = REPORTS_DIR / name
        if src.exists():
            dst = DATA_DIR / name
            shutil.copy2(src, dst)
            copied.append(name)
    print(f"[publish] copiés vers docs/data/: {copied}" if copied else "[publish] aucun JSON trouvé à copier (ok au premier run).")

def write_health(status: str = "ok"):
    # récupère le dernier commit court
    try:
        commit = sh(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT)
    except Exception:
        commit = "unknown"
    payload = {
        "generated_at": int(time.time()),
        "commit": commit,
        "status": status
    }
    (DOCS_DIR / "health.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[publish] écrit docs/health.json")

def pages_url():
    # URL standard GitHub Pages
    owner = GIT_USER or "owner"
    repo  = GIT_REPO or REPO_ROOT.name
    return f"https://{owner}.github.io/{repo}/"

def git_add_commit_push():
    # add/commit/push
    try:
        sh(["git", "add", "docs"], cwd=REPO_ROOT)
        sh(["git", "commit", "-m", "chore(pages): publish dashboard"], cwd=REPO_ROOT, check=False)
        sh(["git", "push", "origin", GIT_BRANCH], cwd=REPO_ROOT)
        print("[publish] push terminé.")
    except Exception as e:
        print(f"[publish] push ignoré: {e}")

def main():
    print(f"[publish] repo={REPO_ROOT}")
    git_config()
    git_remote_with_token()
    copy_reports()
    write_health("ok")
    git_add_commit_push()
    url = pages_url()
    Path(PAGES_URL_OUT).write_text(url, encoding="utf-8")
    print(f"[publish] Pages URL: {url}  (écrit dans {PAGES_URL_OUT})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        write_health(f"error: {e}")
        print(f"[publish] FATAL: {e}")
        sys.exit(1)