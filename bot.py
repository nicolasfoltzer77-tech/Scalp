from __future__ import annotations
import sys, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _clean_py_caches(root: Path) -> None:
    for p in root.rglob("*.pyc"):
        try: p.unlink()
        except Exception: pass
    for d in root.rglob("__pycache__"):
        try: shutil.rmtree(d, ignore_errors=True)
        except Exception: pass

def main() -> int:
    _clean_py_caches(ROOT)
    from engine.app import run_app
    run_app()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())