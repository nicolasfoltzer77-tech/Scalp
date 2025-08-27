#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tools/publish_pages.py

Publie le dashboard statique vers GitHub Pages en utilisant UNIQUEMENT
les variables d'environnement du notebook.

ENV attendues (définies au niveau /notebooks, pas dans le repo):
  GIT_USER      : ex. "nicolasfoltzer77-tech"
  GIT_TOKEN     : PAT GitHub (scope repo)
  GIT_REPO      : nom du repo (ex. "scalp")
  GIT_BRANCH    : branche (ex. "main")        [optionnel, défaut: main]
  GIT_EMAIL     : email pour git config       [optionnel]
  REPO_PATH     : chemin du repo local        [optionnel, défaut: /notebooks/scalp]
  PAGES_URL_OUT : fichier où écrire l'URL     [optionnel, défaut: <repo>/docs/pages_url.txt]

Comportement:
- écrit/rafraîchit docs/index.html / docs/dashboard.html en amont (fait par render_report.py)
- copie reports/*.json -> docs/data/
- écrit docs/health.json (horodatage + commit)
- git add/commit/push vers origin (URL https://<user>:<token>@github.com/<user>/<repo>.git)
- n’affiche jamais le token dans les logs
- GIT_TERMINAL_PROMPT=0 => aucun prompt Username/Password
"""

from __future__ import annotations
import json, os, subprocess, sys, time, shutil
from pathlib import Path

# -------- lecture ENV (depuis l'env du notebook) --------
GIT_USER   = os.environ.get("GIT_USER", "").strip()
GIT_TOKEN  = os.environ.get("GIT_TOKEN", "").strip()
GIT_REPO   = os.environ.get("GIT_REPO", "").strip()
GIT_BRANCH = os.environ.get("GIT_BRANCH", "main").strip()
GIT_EMAIL  = os.environ.get("GIT_EMAIL", f"{GIT_USER}@users.noreply.github.com").strip()
REPO_PATH  = Path(os.environ.get("REPO_PATH", "/notebooks/scalp")).resolve()
PAGES_URL_OUT = os.environ.get("PAGES_URL_OUT", str(REPO_PATH / "docs" / "pages_url.txt"))

REPORTS_DIR = REPO_PATH / "reports"
DOCS_DIR    = REPO_PATH / "docs"
DATA_DIR    = DOCS_DIR / "data"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Git: pas de prompt
os.environ.setdefault("GIT_TERMINAL_PROMPT", "0")

def sh(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    res = subprocess.run(
        args, cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=check,
    )
    return res.stdout.strip()

def git_config():
    try:
        if GIT_USER:
            sh(["git", "config", "user.name", GIT_USER], cwd=REPO_PATH)
        if GIT_EMAIL:
            sh(["git", "config", "user.email", GIT_EMAIL], cwd=REPO_PATH)
    except Exception as e:
        print(f"[publish] warn git_config: {e}")

def git_remote_with_token():
    """Force origin à utiliser une URL https avec token (sans l’afficher)."""
    if not (GIT_USER and GIT_TOKEN and GIT_REPO):
        print("[publish] ❌ GIT_USER / GIT_TOKEN / GIT_REPO manquant(s) dans l'env.")
        return False
    auth_url = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/{GIT_USER}/{GIT_REPO}.git"
    try:
        # init si besoin
        sh(["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO_PATH, check=True)
    except Exception:
        sh(["git", "init"], cwd=REPO_PATH, check=True)

    try:
        cur = sh(["git", "remote", "get-url", "origin"], cwd=REPO_PATH, check=False)
        # on remplace systématiquement (évite prompts)
        sh(["git", "remote", "remove", "origin"], cwd=REPO_PATH, check=False)
    except Exception:
        pass

    try:
        sh(["git", "remote", "add", "origin", auth_url], cwd=REPO_PATH, check=True)
        print("[publish] origin=github (token) ✔")
        return True
    except Exception as e:
        print(f"[publish] ❌ set origin: {e}")
        return False

def copy_reports():
    """Copie quelques artefacts JSON/YML vers docs/data/ (si présents)."""
    candidates = [
        "status.json", "summary.json", "last_errors.json",
        "strategies.yml.next", "strategies.yml",
    ]
    copied = []
    for name in candidates:
        src = REPORTS_DIR / name
        if src.exists():
            dst = DATA_DIR / name
            shutil.copy2(src, dst)
            copied.append(name)
    if copied:
        print(f"[publish] copiés -> docs/data/: {copied}")
    else:
        print("[publish] aucun JSON à copier (ok au premier run).")

def write_health(status: str = "ok"):
    try:
        commit = sh(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_PATH, check=False) or "unknown"
    except Exception:
        commit = "unknown"
    payload = {"generated_at": int(time.time()), "commit": commit, "status": status}
    (DOCS_DIR / "health.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[publish] écrit docs/health.json")

def pages_url() -> str:
    owner = GIT_USER or "owner"
    repo  = GIT_REPO or REPO_PATH.name
    return f"https://{owner}.github.io/{repo}/"

def git_add_commit_push():
    # On commit silencieusement (pas d’échec si rien à commit)
    sh(["git", "add", "docs"], cwd=REPO_PATH, check=False)
    sh(["git", "commit", "-m", "chore(pages): publish dashboard"], cwd=REPO_PATH, check=False)
    sh(["git", "push", "origin", GIT_BRANCH], cwd=REPO_PATH, check=True)
    print(f"[publish] push -> origin/{GIT_BRANCH} ✔")

def main():
    print(f"[publish] repo={REPO_PATH}")
    git_config()
    if not git_remote_with_token():
        return
    copy_reports()
    write_health("ok")
    try:
        git_add_commit_push()
    except Exception as e:
        print(f"[publish] ❌ push: {e}")
        return
    url = pages_url()
    Path(PAGES_URL_OUT).write_text(url, encoding="utf-8")
    print(f"[publish] Pages URL: {url}  (écrit dans {PAGES_URL_OUT})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[publish] FATAL: {e}")
        sys.exit(1)