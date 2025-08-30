#!/usr/bin/env python3
"""
Watch & Publish Dashboard to GitHub Pages (version simple et robuste)
- Copie /opt/scalp/dashboard.html -> docs/index.html
- Ecrit l'URL Pages dans dashboard_url.txt
- Publie en forçant l'alignement sur origin/main (reset --hard) avant commit/push
- DRY_RUN=1 => pas de push (copie locale seulement)

Variables env requises: GIT_USER, GIT_TOKEN, GIT_REPO (owner/repo)
Variables env optionnelles: REPO_PATH (/opt/scalp), DRY_RUN (0/1)
"""
import os, time, shutil, subprocess, sys, shlex
from pathlib import Path

REPO_PATH = Path(os.environ.get("REPO_PATH", "/opt/scalp")).resolve()
DASH = REPO_PATH / "dashboard.html"
DOCS_DIR = REPO_PATH / "docs"
DOCS_INDEX = DOCS_DIR / "index.html"
URL_TXT = REPO_PATH / "dashboard_url.txt"

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
GIT_USER = os.environ.get("GIT_USER")
GIT_TOKEN = os.environ.get("GIT_TOKEN")
GIT_REPO = os.environ.get("GIT_REPO")  # ex: nicolasfoltzer77-tech/Scalp

if not GIT_REPO:
    print("[publish] ERREUR: GIT_REPO non défini (ex: owner/repo).")
    sys.exit(2)

owner, name = (GIT_REPO.split("/", 1) + [""])[:2]
PAGES_URL = f"https://{owner}.github.io/{name}/"

def run(cmd, check=True):
    printable = " ".join(shlex.quote(x) for x in cmd)
    if GIT_TOKEN:
        printable = printable.replace(GIT_TOKEN, "****")
    print("[git]", printable)
    return subprocess.run(cmd, cwd=REPO_PATH, check=check)

def ensure_origin_with_token():
    if not (GIT_USER and GIT_TOKEN):
        print("[publish] Pas de GIT_USER/GIT_TOKEN -> mode local seulement.")
        return False
    origin_url = f"https://{GIT_USER}:{GIT_TOKEN}@github.com/{GIT_REPO}.git"
    run(["git", "remote", "set-url", "origin", origin_url], check=False)
    return True

def hard_sync_main():
    # on se cale sans état intermédiaire (pas de rebase, pas de merge)
    run(["git", "fetch", "origin", "main"])
    run(["git", "checkout", "-B", "main"])
    run(["git", "reset", "--hard", "origin/main"])

def publish_once():
    DOCS_DIR.mkdir(exist_ok=True)
    if not DASH.exists():
        print("[publish] dashboard.html introuvable, rien à publier.")
        return False

    # Copier les artefacts
    shutil.copyfile(DASH, DOCS_INDEX)
    URL_TXT.write_text(PAGES_URL + "\n", encoding="utf-8")
    print(f"[publish] Copié -> docs/index.html ; URL={PAGES_URL}")

    if DRY_RUN:
        print("[publish] DRY_RUN=1 -> pas de push.")
        return True

    if not ensure_origin_with_token():
        print("[publish] Pas de credentials : skip push.")
        return False

    # Toujours s'aligner sur la remote pour éviter les conflits
    # même si quelqu'un a poussé juste avant nous.
    # On recommit ensuite nos fichiers (générés).
    try:
        run(["git", "rebase", "--abort"], check=False)
        run(["git", "merge", "--abort"],  check=False)
        hard_sync_main()

        run(["git", "add", "docs/index.html", "dashboard.html", "dashboard_url.txt"], check=False)
        run(["git", "commit", "-m", "chore(pages): publish dashboard"], check=False)
        run(["git", "push", "origin", "HEAD:main"])

        print("[publish] Push OK.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[publish] Push KO: {e}")
        return False

def main():
    once = "--once" in sys.argv
    last_mtime = DASH.stat().st_mtime if DASH.exists() else 0.0
    publish_once()
    if once:
        return
    while True:
        time.sleep(5)
        if DASH.exists():
            mtime = DASH.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                publish_once()

if __name__ == "__main__":
    main()
