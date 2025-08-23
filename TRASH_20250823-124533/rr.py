#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil, re, os, datetime as dt
from pathlib import Path

# ---------- helpers ----------
def info(msg): print(f"[i] {msg}")
def ok(msg):   print(f"[✓] {msg}")
def warn(msg): print(f"[!] {msg}")

def backup_repo(repo: Path) -> Path:
    ts = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dst = repo.parent / f".backup-refactor-{ts}"
    shutil.copytree(repo, dst)
    ok(f"Sauvegarde créée: {dst}")
    return dst

def ensure_pkg_init(path: Path):
    initp = path / "__init__.py"
    if not initp.exists():
        initp.write_text("# package\n", encoding="utf-8")

def move_dir(src: Path, dst: Path):
    if not src.exists(): return
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        shutil.move(str(child), str(dst / child.name))
    # supprime le répertoire source s'il est vide
    try: src.rmdir()
    except Exception: pass

# règles initiales (rangement)
IMPORT_RULES_STAGE1 = [
    (re.compile(r"from\s+scalp\.config\.loader\s+import\s+load_settings"), "from scalper.config import load_settings"),
    (re.compile(r"from\s+config\.loader\s+import\s+load_settings"), "from scalper.config import load_settings"),
    (re.compile(r"from\s+scalp\.config\s+import\s+load_settings"), "from scalper.config import load_settings"),
    (re.compile(r"from\s+live(\.| import)"), r"from scalper.live\1"),
    (re.compile(r"import\s+live(\s|$)"), r"import scalper.live\1"),
    (re.compile(r"from\s+backtest(\.| import)"), r"from scalper.backtest\1"),
    (re.compile(r"import\s+backtest(\s|$)"), r"import scalper.backtest\1"),
    (re.compile(r"from\s+signals(\.| import)"), r"from scalper.signals\1"),
    (re.compile(r"import\s+signals(\s|$)"), r"import scalper.signals\1"),
    (re.compile(r"from\s+exchange(\.| import)"), r"from scalper.exchange\1"),
    (re.compile(r"import\s+exchange(\s|$)"), r"import scalper.exchange\1"),
]

def rewrite_imports(root: Path, rules):
    changed = 0
    for py in root.rglob("*.py"):
        if ".backup-" in str(py) or ".backup" in str(py):  # safety
            continue
        txt = py.read_text(encoding="utf-8")
        new = txt
        for pat, rep in rules:
            new = pat.sub(rep, new)
        if new != txt:
            py.write_text(new, encoding="utf-8")
            changed += 1
    return changed

def ensure_config_package(scalp_pkg: Path):
    """Transforme scalp/config.py en package scalp/config/loader.py et ajoute __init__.py exportant load_settings."""
    flat = scalp_pkg / "config.py"
    pkg = scalp_pkg / "config"
    loader = pkg / "loader.py"
    initp = pkg / "__init__.py"

    # si un config.py existe, le renommer pour archivage
    if flat.exists():
        legacy = scalp_pkg / "legacy_config.py"
        if legacy.exists(): legacy.unlink()
        shutil.move(str(flat), str(legacy))
        info(f"renommé {flat} -> {legacy}")

    pkg.mkdir(parents=True, exist_ok=True)
    ensure_pkg_init(pkg)

    # si pas de loader.py, créer un loader minimal (tu pourras le remplacer par ta version complète)
    if not loader.exists():
        loader.write_text(
            'from __future__ import annotations\n'
            'import os, json\n'
            'from typing import Any, Dict, Tuple\n'
            'try:\n'
            '    import yaml\n'
            'except Exception:\n'
            '    yaml = None\n'
            'try:\n'
            '    from dotenv import load_dotenv\n'
            'except Exception:\n'
            '    load_dotenv = None\n'
            '\n'
            'def _read_yaml(path: str):\n'
            '    if not os.path.exists(path): return {}\n'
            '    with open(path, "r", encoding="utf-8") as f:\n'
            '        if yaml: return yaml.safe_load(f) or {}\n'
            '        return json.load(f)\n'
            '\n'
            'def load_settings(config_path: str="config.yml", config_local_path: str="config.local.yml"):\n'
            '    if load_dotenv: load_dotenv(override=False)\n'
            '    base = _read_yaml(config_path)\n'
            '    local = _read_yaml(config_local_path)\n'
            '    cfg = {**base, **local}\n'
            '    runtime = {\n'
            '        "quiet": bool(cfg.get("QUIET", 1)),\n'
            '        "print_sample": bool(cfg.get("PRINT_OHLCV_SAMPLE", 0)),\n'
            '        "timeframe": str(cfg.get("TIMEFRAME", "5m")),\n'
            '        "cash": float(cfg.get("CASH", 10000)),\n'
            '        "risk_pct": float(cfg.get("RISK_PCT", 0.5)),\n'
            '        "slippage_bps": float(cfg.get("SLIPPAGE_BPS", 2)),\n'
            '        "watchlist_mode": str(cfg.get("WATCHLIST_MODE", "local")),\n'
            '        "watchlist_local_conc": int(cfg.get("WATCHLIST_LOCAL_CONC", 5)),\n'
            '        "top_symbols": cfg.get("TOP_SYMBOLS", []),\n'
            '        "top_candidates": cfg.get("TOP_CANDIDATES", []),\n'
            '        "caps": cfg.get("CAPS", {}),\n'
            '        "fees_by_symbol": {},\n'
            '    }\n'
            '    secrets = {\n'
            '        "BITGET_API_KEY": os.getenv("BITGET_API_KEY", ""),\n'
            '        "BITGET_API_SECRET": os.getenv("BITGET_API_SECRET", ""),\n'
            '        "BITGET_API_PASSWORD": os.getenv("BITGET_API_PASSWORD", ""),\n'
            '        "BITGET_USE_TESTNET": os.getenv("BITGET_USE_TESTNET", "1") in ("1","true","True"),\n'
            '        "BITGET_PRODUCT": os.getenv("BITGET_PRODUCT", "umcbl"),\n'
            '        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),\n'
            '        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),\n'
            '    }\n'
            '    return runtime, secrets\n',
            encoding="utf-8"
        )
    # __init__.py exporte load_settings
    initp.write_text("from .loader import load_settings\n__all__ = ['load_settings']\n", encoding="utf-8")

def stage1_restructure(repo: Path):
    """Range les modules à l’intérieur du package 'scalp/' + fix imports."""
    scalp_pkg = repo / "scalp"
    scalp_pkg.mkdir(exist_ok=True)
    ensure_pkg_init(scalp_pkg)

    for mod in ("live", "backtest", "signals", "config", "exchange"):
        src = repo / mod
        if src.exists() and src.is_dir():
            dst = scalp_pkg / mod
            info(f"déplacement {src} -> {dst}")
            move_dir(src, dst)
            ensure_pkg_init(dst)

    # gérer config.py -> package config/loader.py
    ensure_config_package(scalp_pkg)

    # réécriture imports vers scalper.*
    changed = rewrite_imports(repo, IMPORT_RULES_STAGE1)
    ok(f"imports stage1 réécrits dans {changed} fichier(s)")

def stage2_rename_package(repo: Path, old="scalp", new="scalper"):
    """Renomme le package interne old -> new et réécrit tous les imports."""
    pkg_old = repo / old
    pkg_new = repo / new
    if not pkg_old.exists():
        warn(f"package {pkg_old} introuvable (déjà renommé ?)")
    else:
        shutil.move(str(pkg_old), str(pkg_new))
        ok(f"package renommé {pkg_old.name} -> {pkg_new.name}")

    # réécriture imports 'old.' -> 'new.'
    pat = re.compile(rf"\b{old}\.")
    changed = 0
    for py in repo.rglob("*.py"):
        if ".backup" in str(py): continue
        txt = py.read_text(encoding="utf-8")
        new_txt = pat.sub(f"{new}.", txt)
        if new_txt != txt:
            py.write_text(new_txt, encoding="utf-8")
            changed += 1
    ok(f"imports stage2 réécrits dans {changed} fichier(s)")

def main():
    ap = argparse.ArgumentParser(description="Restructure + rename Python package (scalp -> scalper).")
    ap.add_argument("--repo", default="./", help="Chemin du repo (racine qui contient bot.py).")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    if not repo.exists(): raise SystemExit(f"Repo introuvable: {repo}")

    # 1) sauvegarde
    backup_repo(repo)

    # 2) ranger les modules sous scalp/ (package) + fixer imports
    stage1_restructure(repo)

    # 3) renommer le package interne scalp/ -> scalper/ + fixer imports
    stage2_rename_package(repo, old="scalp", new="scalper")

    ok("Refactor complet terminé.")
    print("\n➡️ Vérifie maintenant:\n"
          "   python - <<'PY'\n"
          "import importlib; m = importlib.import_module('scalper.config'); print('OK:', hasattr(m, 'load_settings'))\n"
          "PY\n"
          "\nPuis lance:\n"
          "   python bot.py\n")

if __name__ == "__main__":
    main()