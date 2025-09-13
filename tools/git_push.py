#!/usr/bin/env python3
import os, subprocess, sys

def run(cmd, check=True):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=check)

# Charger les variables depuis /etc/scalp.env
envfile = "/etc/scalp.env"
if os.path.exists(envfile):
    with open(envfile) as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)

user = os.getenv("GIT_USER")
token = os.getenv("GIT_TOKEN")
repo = os.getenv("GIT_REPO")

if not (user and token and repo):
    print("❌ Variables GIT_USER, GIT_TOKEN, GIT_REPO manquantes dans /etc/scalp.env", file=sys.stderr)
    sys.exit(1)

# Construire l’URL avec token
url = f"https://{user}:{token}@{repo}"

# Ajouter remote si absent
try:
    remotes = subprocess.check_output(["git", "remote"], text=True).split()
    if "origin" not in remotes:
        run(["git", "remote", "add", "origin", url])
    else:
        run(["git", "remote", "set-url", "origin", url])
except Exception as e:
    print("⚠️ Impossible de configurer remote:", e)

# Push branche courante
branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
run(["git", "push", "origin", branch])
