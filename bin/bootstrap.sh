#!/usr/bin/env bash
set -Eeuo pipefail

# resolve repo root (works from anywhere)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "[bootstrap] repo: $ROOT"

# 0) bypass any auto bootstrap while we install
export SCALP_SKIP_BOOT=1

# 1) create/repair venv here (and only here)
if ! command -v python3 >/dev/null; then
  echo "[bootstrap] FATAL: python3 introuvable"; exit 127
fi
PY="$(command -v python3)"
echo "[bootstrap] python: $PY ($("$PY" -V))"

rm -rf "$ROOT/venv"
"$PY" -m venv --system-site-packages "$ROOT/venv"

# shellcheck disable=SC1091
source "$ROOT/venv/bin/activate"

python -m pip install --upgrade pip setuptools wheel
# install with our pins; use --no-cache-dir to avoid partial wheels if low RAM
pip install --no-cache-dir -r "$ROOT/requirements.txt"

# 2) quick sanity check: can we import the essentials?
python - <<'PY'
mods = ["yaml","tqdm","scipy","optuna","pandas","numpy"]
ok=True
for m in mods:
    try:
        __import__(m)
    except Exception as e:
        print(f"[bootstrap] MISS {m}: {e}")
        ok=False
if not ok:
    raise SystemExit(1)
print("[bootstrap] ✅ imports OK")
PY

# ensure all sh/py in repo are executable
find "$ROOT" -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \; || true
echo "[bootstrap] chmod +x applied to *.sh and *.py"

echo "[bootstrap] done."