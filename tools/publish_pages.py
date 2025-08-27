#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json, os, subprocess, sys, time, shutil
from pathlib import Path

REPO_PATH  = Path(os.environ.get("REPO_PATH", "/notebooks/scalp")).resolve()
DOCS_DIR   = REPO_PATH / "docs"
DATA_DIR   = DOCS_DIR / "data"
REPORTS_DIR= REPO_PATH / "reports"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("GIT_TERMINAL_PROMPT", "0")

def _load_dotenv_if_needed():
    """Charge /notebooks/.env si GIT_USER/TOKEN/REPO manquent."""
    need = any(not os.environ.get(k) for k in ("GIT_USER","GIT_TOKEN","GIT_REPO"))
    if not need:
        return
    for candidate in ("/notebooks/.env", "/notebooks/scalp/.env"):
        p = Path(candidate)
        if not p.exists():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    # ne pas écraser si déjà défini
                    os.environ.setdefault(k, v)
            print(f"[publish] .env chargé depuis {p}")
            break
        except Exception as e:
            print(f"[publish] warn: lecture {p}: {e}")

def sh(args, cwd: Path|None=None, check=True)->str:
    r = subprocess.run(args, cwd=str(cwd) if cwd else None,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, check=check)
    return r.stdout.strip()

def git_config(user, email):
    try:
        sh(["git","config","user.name", user],  cwd=REPO_PATH)
        sh(["git","config","user.email",email], cwd=REPO_PATH)
    except Exception as e:
        print(f"[publish] warn git_config: {e}")

def git_remote_with_token(user, token, repo, branch):
    try:
        sh(["git","rev-parse","--is-inside-work-tree"], cwd=REPO_PATH, check=True)
    except Exception:
        sh(["git","init"], cwd=REPO_PATH, check=True)
    auth = f"https://{user}:{token}@github.com/{user}/{repo}.git"
    sh(["git","remote","remove","origin"], cwd=REPO_PATH, check=False)
    sh(["git","remote","add","origin", auth], cwd=REPO_PATH, check=True)
    print("[publish] origin=github (token) ✔")

def copy_reports():
    copied=[]
    for name in ("status.json","summary.json","last_errors.json","strategies.yml.next","strategies.yml"):
        src = REPORTS_DIR / name
        if src.exists():
            shutil.copy2(src, DATA_DIR / name)
            copied.append(name)
    if copied:
        print(f"[publish] copiés -> docs/data/: {copied}")
    else:
        print("[publish] aucun JSON à copier (ok au premier run).")

def write_health(status="ok"):
    try:
        commit = sh(["git","rev-parse","--short","HEAD"], cwd=REPO_PATH, check=False) or "unknown"
    except Exception:
        commit = "unknown"
    payload = {"generated_at": int(time.time()), "commit": commit, "status": status}
    (DOCS_DIR / "health.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[publish] écrit docs/health.json")

def pages_url(user, repo) -> str:
    return f"https://{user}.github.io/{repo}/"

def git_add_commit_push(branch):
    sh(["git","add","docs"], cwd=REPO_PATH, check=False)
    sh(["git","commit","-m","chore(pages): publish dashboard"], cwd=REPO_PATH, check=False)
    sh(["git","push","origin", branch], cwd=REPO_PATH, check=True)
    print(f"[publish] push -> origin/{branch} ✔")

def main():
    _load_dotenv_if_needed()

    user  = os.environ.get("GIT_USER","").strip()
    token = os.environ.get("GIT_TOKEN","").strip()
    repo  = os.environ.get("GIT_REPO","").strip()
    branch= os.environ.get("GIT_BRANCH","main").strip()
    email = os.environ.get("GIT_EMAIL", f"{user}@users.noreply.github.com").strip()

    print(f"[publish] repo={REPO_PATH}")
    if not (user and token and repo):
        print("[publish] ❌GIT_USER / GIT_TOKEN / GIT_REPO manquant(s) dans l'env.")
        return

    git_config(user, email)
    git_remote_with_token(user, token, repo, branch)
    copy_reports()
    write_health("ok")
    git_add_commit_push(branch)

    url = pages_url(user, repo)
    out = REPO_PATH / "docs" / "pages_url.txt"
    out.write_text(url, encoding="utf-8")
    print(f"[publish] Pages URL: {url} (écrit dans {out})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[publish] FATAL: {e}")
        sys.exit(1)