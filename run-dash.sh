#!/bin/bash
cd "$(dirname "$0")"
echo "[*] Lancement du dashboard Streamlit..."
streamlit run dash/app.py --server.port 8501 --server.headless true