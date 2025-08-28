#!/usr/bin/env bash
set -Eeuo pipefail

# resolve repo root
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# load env (optional)
set -a
[ -f /etc/scalp.env ] && . /etc/scalp.env
[ -f .env ] && . ./.env
set +a

LOG_DIR="$ROOT/logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/render-$(date -u +%Y%m%d-%H%M%S).log"

# log to file + screen
exec > >(tee -a "$LOG") 2>&1
echo "[safe] start…"; echo "python: $(python3 -V)"; echo "root: $ROOT"

# ensure venv here, not /venv at FS root
if [ ! -x "$ROOT/venv/bin/python" ]; then
  echo "[safe] venv absent → bootstrap…"
  "$ROOT/bin/bootstrap.sh"
fi

# activate venv
# shellcheck disable=SC1091
. "$ROOT/venv/bin/activate"

# --- patch ${cls} -> ${{cls}} in tools/render_report.py (idempotent) ---
if [ -f tools/render_report.py ]; then
  python - <<'PY'
from pathlib import Path, re as _re
p=Path("tools/render_report.py")
s=p.read_text(encoding="utf-8")
s2=_re.sub(r"\$\{(\s*cls\s*)\}", r"${{\1}}", s)
if s2!=s:
    p.write_text(s2, encoding="utf-8")
    print("[safe] patched ${cls} → ${{cls}}")
else:
    print("[safe] patch already applied")
PY
else
  echo "[safe] FATAL: tools/render_report.py manquant"; exit 3
fi

# guarantee tools is a package
[ -f tools/__init__.py ] || : > tools/__init__.py

# fix fragile optional dep: bottleneck <1.4 with numpy 1.26.x
python - <<'PY'
try:
    import bottleneck, numpy
    from packaging.version import Version
    if Version(getattr(bottleneck,'__version__','0')) >= Version("1.4"):
        print("[safe] forcing bottleneck<1.4 for numpy 1.26.x")
        import subprocess, sys
        subprocess.check_call([sys.executable,"-m","pip","install","--no-cache-dir","'bottleneck<1.4'"])
except Exception as e:
    print("[safe] bottleneck check skipped:", e)
PY

# run with explicit PYTHONPATH to be safe
export PYTHONPATH="$ROOT"
if python -m tools.render_report; then
  echo "[safe] ✅ rendu OK"
  rc=0
else
  rc=$?; echo "[safe] ❌ KO (rc=$rc)"
fi

echo "[safe] log: $LOG"
exit $rc