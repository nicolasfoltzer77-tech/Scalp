#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCALP - Render report → écrit dashboard.html + index.html dans /docs
et déclenche publication auto vers GitHub Pages.
"""

import os, sys, json, time
from pathlib import Path
from engine.utils.io import load_json
from tools.render_html import render_html

# --- constants ---
REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR  = REPO_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    # 1) config
    cfg = {"generated_at": int(time.time())}
    reports_dir = REPO_ROOT / "scalp_data" / "reports"

    # 2) lire data
    status  = load_json(reports_dir / "status.json")
    summary = load_json(reports_dir / "summary.json")
    last    = load_json(reports_dir / "last_errors.json")

    # 3) render
    html = render_html(cfg, status, summary, last)

    # 4) écrire vers /docs
    index_path = DOCS_DIR / "index.html"
    dash_path  = DOCS_DIR / "dashboard.html"

    index_path.write_text(html, encoding="utf-8")
    dash_path.write_text(html,  encoding="utf-8")

    print(f"[render] Dashboard écrit → {index_path}")

    # 5) publier (git)
    try:
        from tools.publish_pages import main as publish_pages_main
        publish_pages_main()
    except Exception as e:
        print(f"[render] publication GitHub Pages ignorée: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[render] FATAL: {e}")
        sys.exit(1)