#!/usr/bin/env python3
"""
jobs/dash.py — Lance le dashboard Streamlit du projet scalp
Usage:
    python jobs/dash.py
Options:
    --port 8501       Port HTTP (défaut 8501)
    --headless true   Mode headless (recommandé en remote)
"""

import argparse
import subprocess
import sys
from pathlib import Path

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8501, help="Port HTTP (défaut 8501)")
    ap.add_argument("--headless", action="store_true", help="Force mode headless")
    args = ap.parse_args(argv)

    app_path = Path(__file__).resolve().parents[1] / "dash" / "app.py"
    if not app_path.exists():
        sys.exit(f"Dashboard introuvable: {app_path}")

    cmd = [
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(args.port),
    ]
    if args.headless:
        cmd += ["--server.headless", "true"]

    print(f"[i] Lancement du dashboard Streamlit sur port {args.port} ...")
    print(" ".join(cmd))
    subprocess.run(cmd)

if __name__ == "__main__":
    main()