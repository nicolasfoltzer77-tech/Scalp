# scalper/selfcheck.py
from __future__ import annotations
import os, sys, importlib, traceback
from pathlib import Path

NOTEBOOKS = Path("/notebooks")
REPO = (NOTEBOOKS / "scalp") if NOTEBOOKS.exists() else Path(__file__).resolve().parents[2]

def _mask(val: str) -> str:
    if not val: return ""
    return (val[:3] + "…" + val[-3:]) if len(val) > 6 else "********"

def _try_import(modname: str):
    try:
        m = importlib.import_module(modname)
        return True, m
    except Exception:
        return False, traceback.format_exc()

def preflight(verbose: bool = False) -> list[str]:
    """
    Retourne la liste des 'issues' trouvées (vide si tout est OK).
    Ne lève pas d'exception. N'écrit que de l'info lisible.
    """
    issues: list[str] = []
    # s'assurer que le repo est bien dans sys.path
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))

    print("=== SCALPER PREFLIGHT ===")
    print(f"[i] Repo: {REPO}")
    print(f"[i] Python: {sys.version.split()[0]}")

    # backtest API
    ok, mod = _try_import("scalper.backtest")
    if not ok:
        print("[✗] Import scalper.backtest KO")
        if verbose: print(mod)  # ici 'mod' contient la trace
        issues.append("backtest import")
    else:
        has_single = hasattr(mod, "run_single")
        has_multi  = hasattr(mod, "run_multi")
        print(f"[✓] scalper.backtest: run_single={has_single} run_multi={has_multi}")
        if not (has_single and has_multi):
            issues.append("backtest API incomplète")

    # trade_utils
    ok, mod = _try_import("scalper.trade_utils")
    if not ok:
        print("[✗] Import scalper.trade_utils KO")
        if verbose: print(mod)
        issues.append("trade_utils import")
    else:
        print(f"[✓] scalper.trade_utils: compute_position_size={'compute_position_size' in dir(mod)}")

    # fees
    ok, mod = _try_import("scalper.exchange.fees")
    if not ok:
        print("[✗] Import scalper.exchange.fees KO")
        if verbose: print(mod)
        issues.append("fees import")
    else:
        need = {"get_fee", "load_bitget_fees"}
        miss = [n for n in need if not hasattr(mod, n)]
        if miss: issues.append("fees API manquante: " + ",".join(miss))
        print("[✓] scalper.exchange.fees OK")

    # notify/commands/backtest_telegram/orchestrator
    for name, required in [
        ("scalper.live.notify", ("build_notifier_and_stream",)),
        ("scalper.live.commands", ("CommandHandler",)),
        ("scalper.live.backtest_telegram", ("handle_backtest_command",)),
        ("scalper.live.orchestrator", ("run_orchestrator", "Orchestrator")),
    ]:
        ok, mod = _try_import(name)
        if not ok:
            print(f"[✗] Import {name} KO")
            if verbose: print(mod)
            issues.append(f"{name} import")
        else:
            miss = [a for a in required if not hasattr(mod, a)]
            if miss: issues.append(f"{name} API manquante: {','.join(miss)}")
            print(f"[✓] {name} OK")

    # ENV (masqué)
    tg_t = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_c = os.getenv("TELEGRAM_CHAT_ID", "")
    gu   = os.getenv("GIT_USER", "")
    gt   = os.getenv("GIT_TOKEN", "")
    print("\n-- ENV --")
    print(f"  TELEGRAM_BOT_TOKEN: {_mask(tg_t)} {'(ABSENT)' if not tg_t else ''}")
    print(f"  TELEGRAM_CHAT_ID  : {_mask(tg_c)} {'(ABSENT)' if not tg_c else ''}")
    print(f"  GIT_USER          : {gu or '(ABSENT)'}")
    print(f"  GIT_TOKEN         : {_mask(gt)} {'(ABSENT)' if not gt else ''}")

    # Data
    data_dir = (REPO / "data")
    print("\n-- DATA --")
    if data_dir.exists():
        csvs = list(data_dir.glob("*.csv"))
        print(f"  {len(csvs)} CSV trouvé(s) dans data/ (OK si tu backtestes via CSV)")
    else:
        print("  data/ absent (OK si loader API)")

    return issues

def preflight_or_die(verbose: bool = False) -> None:
    issues = preflight(verbose=verbose)
    if issues:
        print("\n[✗] Préflight a détecté des problèmes :")
        for it in issues: print("   -", it)
        print("\nConseils :")
        print(" - Vérifie les fichiers remplacés (backtest/__init__.py, trade_utils.py, exchange/fees.py).")
        print(" - Évite d'importer optimize/walkforward dans backtest/__init__.py.")
        print(" - Charge /notebooks/.env si TELEGRAM/GIT sont absents (source /notebooks/.env).")
        raise SystemExit(1)
    print("\n[✓] Préflight OK — démarrage du bot.")