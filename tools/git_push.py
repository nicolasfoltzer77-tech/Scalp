#!/usr/bin/env python3
import os, sys, subprocess, shlex, datetime, pathlib

REPO_DIR = pathlib.Path("/opt/scalp")
ENV_FILE = "/etc/scalp.env"     # doit fournir GIT_USER et GIT_TOKEN (optionnel GIT_NAME, GIT_EMAIL)

def run(cmd, cwd=REPO_DIR, check=True):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    p = subprocess.run(cmd, cwd=str(cwd), text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode != 0:
        raise RuntimeError(f"CMD fail: {' '.join(cmd)}\n{p.stdout}")
    return p.stdout.strip()

def git(*args, check=True):
    return run(["git", *args], check=check)

def load_env(env_path):
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Env not found: {env_path}")
    with open(env_path) as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: 
                continue
            k,v = line.split("=",1)
            os.environ.setdefault(k.strip(), v.strip())

def ensure_repo():
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    if not (REPO_DIR / ".git").exists():
        git("init")
    # config user si présent
    name = os.getenv("GIT_NAME", os.getenv("GIT_USER", "scalp-bot"))
    email = os.getenv("GIT_EMAIL", f"{name}@local")
    git("config", "user.name", name)
    git("config", "user.email", email)

def current_branch():
    out = git("rev-parse", "--abbrev-ref", "HEAD", check=False)
    return out if out and "HEAD" not in out else None

def has_commit():
    return subprocess.run(["git","rev-parse","--verify","HEAD"],
                          cwd=str(REPO_DIR), stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0

def set_main_branch():
    # force la branche par défaut à main
    git("branch","-M","main")

def set_remote():
    user = os.environ["GIT_USER"]
    token = os.environ["GIT_TOKEN"]
    # Repo voulu: scalp.git (et pas scalp-bot.git)
    repo_path = os.getenv("GIT_REPO", f"{user}/scalp.git")
    authed = f"https://{user}:{token}@github.com/{repo_path}"
    # crée/maj origin
    existing = git("remote", check=False)
    if "origin" in (existing or ""):
        git("remote","set-url","origin",authed)
    else:
        git("remote","add","origin",authed)
    return authed

def index_has_changes():
    # fichiers non suivis ou modifiés en staging ?
    rc = subprocess.run(["git","diff","--cached","--quiet"],
                        cwd=str(REPO_DIR)).returncode
    if rc != 0: 
        return True
    rc2 = subprocess.run(["git","diff","--quiet"],
                         cwd=str(REPO_DIR)).returncode
    if rc2 != 0:
        # stage tout si diff woktree
        git("add","-A")
        return True
    # aussi untracked ?
    un = git("ls-files","--others","--exclude-standard")
    if un:
        git("add","-A"); 
        return True
    return False

def main():
    load_env(ENV_FILE)
    for k in ("GIT_USER","GIT_TOKEN"):
        if not os.getenv(k):
            raise RuntimeError(f"{k} absent dans {ENV_FILE}")

    ensure_repo()

    # .gitignore minimal si absent
    gi = REPO_DIR/".gitignore"
    if not gi.exists():
        gi.write_text("\n".join([
            "__pycache__/",
            "*.pyc",
            ".env*",
            "env*/",
            ".venv*/",
            "data/**",
            "logs/**",
            "nohup.out",
        ])+"\n")

    git("add","-A")
    msg = " ".join(sys.argv[1:]) or f"Sync {datetime.datetime.utcnow().isoformat(timespec='seconds')}Z"
    created_initial = False

    if not has_commit():
        # premier commit
        if index_has_changes():
            git("commit","-m",msg)
        else:
            # force un commit vide pour initialiser
            git("commit","--allow-empty","-m","Initial commit")
        created_initial = True
        set_main_branch()
    else:
        # commits suivants
        if index_has_changes():
            git("commit","-m",msg)

    remote_url = set_remote()

    # push (toujours -u pour setter upstream si besoin)
    try:
        out = git("push","-u","origin","main")
    except Exception as e:
        # masque token en log si erreur
        safe = remote_url.replace(os.environ["GIT_TOKEN"],"***")
        raise RuntimeError(f"Push failed to {safe}\n{e}")

    # Résumé
    br = current_branch() or "main"
    print(f"OK: pushed branch '{br}' to origin.\nInitial: {created_initial}")
    print("Remote set:", remote_url.replace(os.environ["GIT_TOKEN"],"***"))

if __name__ == "__main__":
    main()
