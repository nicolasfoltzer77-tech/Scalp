#!/bin/bash
cd "$(dirname "$0")"
echo "[*] Lancement du dashboard Streamlit..."
# tente python -m pip install -r si jamais le bootstrap n'a pas tourné
python -m pip install -r requirements.txt >/dev/null 2>&1 || true
streamlit run dash/app.py --server.port 8501 --server.headless true