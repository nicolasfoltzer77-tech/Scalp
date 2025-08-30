# jobs/generate_dashboard.py
from __future__ import annotations
import json, os, time
from pathlib import Path

def build_dashboard(reports_dir: str, out_html: str):
    rd = Path(reports_dir)
    cards = []
    for f in sorted(rd.glob("*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        cards.append(f"""
        <div class="card">
          <h3>{j['symbol']} — {j['tf']}</h3>
          <p>Last close: <b>{j['last_close']}</b></p>
          <p>Position: <b>{j['position']}</b></p>
          <p>PNL: <b>{j['pnl']}</b></p>
          <p>Updated: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(j['updated_at']))} UTC</p>
        </div>
        """)
    html = f"""<!doctype html><html><head>
    <meta charset="utf-8"><title>Scalp Dashboard</title>
    <style>
    body{{font-family:system-ui,Arial;margin:20px;background:#0b0f1a;color:#e8eefc}}
    h1{{margin-bottom:10px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}}
    .card{{background:#141b2d;border:1px solid #24314d;border-radius:10px;padding:12px}}
    b{{color:#8bd8bd}}
    </style></head><body>
    <h1>Scalp Dashboard</h1>
    <div class="grid">{''.join(cards) or '<i>No reports yet.</i>'}</div>
    </body></html>"""
    Path(out_html).write_text(html, encoding="utf-8")

if __name__ == "__main__":
    reports = os.environ.get("REPORTS_DIR", "/opt/scalp/reports")
    out = os.environ.get("DASH_HTML", "/opt/scalp/dashboard.html")
    build_dashboard(reports, out)
    print(f"[dashboard] built -> {out}")
