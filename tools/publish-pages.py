#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Publication GitHub Pages SANS PROMPT.

- Copie les artefacts vers /docs :
  * HTML : docs/index.html, docs/dashboard.html (déjà écrits par render_report)
  * JSON : docs/data/{summary.json,status.json,last_errors.json}
  * Health : docs/health.json (timestamp + commit + état)
- Commit + push via token (env: GIT_USER, GIT_TOKEN, GIT_REPO, GIT_BRANCH)
- N'échoue pas le process principal si pas de token ou si aucune modif
"""

from __future__ import annotations
import os, sys, shutil, subprocess, json, time
from pathlib import Path

os.environ["GIT_TERMINAL_PROMPT"] = "0"

def sh(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=check)

def time_utc() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

def write_health(docs_dir: Path, push_status: str) -> None:
    health_path = docs_dir / "health.json"
    commit = "unknown"
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(docs_dir.parent),
            capture_output=True, text=True, check=True
        )
        commit = out.stdout.strip()
    except Exception:
        pass
    payload = {
        "generated_at": time_utc(),
        "commit": commit,
        "status": push_status,
    }
    health_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[publish] health.json écrit → {health_path}")

def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]   # <repo>
    docs_dir  = repo_root / "docs"
    data_dir  = docs_dir / "data"
    docs_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    # --- copier JSON depuis reports ---
    reports_candidates = [
        Path("/notebooks/scalp_data/reports"),
        repo_root / "scalp_data" / "reports",
    ]
    reports_dir = next((p for p in reports_candidates if p.exists()), None)
    if reports_dir:
        for name in ("summary.json", "status.json", "last_errors.json"):
            src, dst = reports_dir / name, data_dir / name
            if src.exists():
                shutil.copy2(src, dst)
                print(f"[publish] Copié {src} -> {dst}")
    else:
        print("[publish] Aucun reports_dir trouvé, skip JSON.")

    # --- infos Git ---
    user   = os.environ.get("GIT_USER", "").strip()
    token  = os.environ.get("GIT_TOKEN", "").strip()
    repo   = os.environ.get("GIT_REPO", "Scalp").strip()
    branch = os.environ.get("GIT_BRANCH", "main").strip()

    if not user or not token:
        print("[publish] GIT_USER/GIT_TOKEN absents -> push ignoré (local OK).")
        write_health(docs_dir, "local-only")
        return

    origin_url = f"https://x-access-token:{token}@github.com/{user}/{repo}.git"

    # --- config Git ---
    try:
        try: sh(["git","config","user.email"], repo_root)
        except subprocess.CalledProcessError:
            sh(["git","config","user.email",f"{user}@users.noreply.github.com"], repo_root)
        try: sh(["git","config","user.name"], repo_root)
        except subprocess.CalledProcessError:
            sh(["git","config","user.name",user], repo_root)

        rem = sh(["git","remote"], repo_root, check=False).stdout.split()
        if "origin" in rem:
            sh(["git","remote","set-url","origin",origin_url], repo_root)
        else:
            sh(["git","remote","add","origin",origin_url], repo_root)
    except subprocess.CalledProcessError as e:
        print("[publish] ⚠️ config git échouée:", e.stderr.strip())
        write_health(docs_dir, "git-config-error")
        return

    # --- stage docs ---
    try: sh(["git","add","docs"], repo_root)
    except subprocess.CalledProcessError as e:
        print("[publish] ⚠️ git add échoué:", e.stderr.strip())
        write_health(docs_dir, "git-add-error")
        return

    # --- commit si changements ---
    if subprocess.run(["git","diff","--cached","--quiet"], cwd=str(repo_root)).returncode == 0:
        print("[publish] Aucun changement.")
        write_health(docs_dir, "no-changes")
        return

    try: sh(["git","commit","-m",f"pages: update at {time_utc()}"], repo_root)
    except subprocess.CalledProcessError as e:
        print("[publish] ⚠️ git commit échoué:", e.stderr.strip())
        write_health(docs_dir, "git-commit-error")
        return

    # --- push ---
    try:
        sh(["git","push","origin",f"HEAD:{branch}"], repo_root)
        print("[publish] ✅ Push OK.")
        write_health(docs_dir, "push-ok")
    except subprocess.CalledProcessError as e:
        print("[publish] ❌ Push KO:", e.stderr.strip())
        write_health(docs_dir, "push-failed")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[publish] FATAL: {exc}")
        sys.exit(1)