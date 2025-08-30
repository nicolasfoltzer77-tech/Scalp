# -*- coding: utf-8 -*-
"""
Dashboard minimal, robuste et rapide.
- Lit /opt/scalp/engine/config/config.yaml (runtime.tf_list, data_dir, reports_dir)
- Lit /opt/scalp/reports/watchlist.json ({"symbols":[...]}) si présent, sinon fallback bootstrap/manual/symbols
- Marque "OK" si data/<SY>/<TF>/ohlcv.json existe, sinon "…"
- Jamais de KeyError: .get() partout
"""

from __future__ import annotations
import json, yaml, os, sys, datetime
from pathlib import Path
from html import escape as esc

CFG_PATH = Path("/opt/scalp/engine/config/config.yaml")
OUT_HTML = Path(os.environ.get("DASH_HTML", "/opt/scalp/dashboard.html"))

def utc_now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def load_cfg():
    cfg = yaml.safe_load(CFG_PATH.read_text(encoding="utf-8"))
    rt  = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    data_dir    = rt.get("data_dir", "/opt/scalp/data")
    reports_dir = rt.get("reports_dir", "/opt/scalp/reports")
    tf_list     = list(rt.get("tf_list", ["1m"]))
    # symbol fallbacks
    bootstrap   = rt.get("bootstrap_symbols") or []
    manual_keep = rt.get("manual_symbols") or []
    symbols_fb  = rt.get("symbols") or []
    fallback    = list(dict.fromkeys([*bootstrap, *manual_keep, *symbols_fb])) or ["BTCUSDT","ETHUSDT"]
    return data_dir, reports_dir, tf_list, fallback

def load_watchlist(reports_dir: str, fallback_syms: list[str]) -> list[str]:
    wl = Path(reports_dir) / "watchlist.json"
    if wl.exists():
        try:
            o = json.loads(wl.read_text(encoding="utf-8"))
            syms = o.get("symbols") or []
            # normalisation simple: garde que les *USDT
            syms = [s for s in syms if isinstance(s, str) and s.upper().endswith("USDT")]
            if syms:
                return list(dict.fromkeys(syms))
        except Exception:
            pass
    # fallback
    return [s for s in fallback_syms if isinstance(s,str) and s.upper().endswith("USDT")]

def data_ok(data_dir: str, sy: str, tf: str) -> bool:
    p = Path(data_dir) / sy / tf / "ohlcv.json"
    return p.exists() and p.stat().st_size > 0

def badge(ok: bool) -> str:
    return f'<span style="display:inline-block;padding:.08rem .35rem;border-radius:.5rem;font-size:.8rem;background:{("#d1fae5" if ok else "#fef3c7")};color:{("#065f46" if ok else "#92400e")};">{("OK" if ok else "…")}</span>'

def build_html(symbols: list[str], tf_list: list[str], data_dir: str) -> str:
    rows = []
    for sy in symbols:
        cells = [f"<td><b>{esc(sy)}</b></td>"]
        for tf in tf_list:
            ok = data_ok(data_dir, sy, tf)
            cells.append(f"<td style='text-align:center'>{badge(ok)}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    heads = "".join([f"<th style='text-align:center'>{esc(tf)}</th>" for tf in tf_list])
    table = f"""
    <table style="border-collapse:collapse;width:100%">
      <thead><tr><th>Symbol</th>{heads}</tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="99">No symbols.</td></tr>'}</tbody>
    </table>
    """
    css = """
    <style>
      body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,'Helvetica Neue',Arial,sans-serif;margin:20px;line-height:1.42}
      h1{font-size:1.4rem;margin:.2rem 0}
      .muted{color:#6b7280;font-size:.9rem}
      th,td{border-bottom:1px solid #e5e7eb;padding:.35rem .5rem}
      thead th{border-bottom:2px solid #9ca3af;background:#f3f4f6}
    </style>
    """
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Scalp Dashboard</title>{css}
<body>
  <h1>Scalp Dashboard</h1>
  <div class="muted">Updated: {esc(utc_now())}</div>
  <div class="muted">TFs: {', '.join(map(esc, tf_list))}</div>
  <hr>
  {table}
</body></html>"""

def main():
    data_dir, reports_dir, tf_list, fb = load_cfg()
    symbols = load_watchlist(reports_dir, fb)
    html = build_html(symbols, tf_list, data_dir)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"[dashboard] built -> {OUT_HTML}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # n'échoue jamais silencieusement: écris un HTML d'erreur pour Pages
        err = f"""<!doctype html><meta charset="utf-8"><pre>Dashboard error: {type(e).__name__}: {e}</pre>"""
        OUT_HTML.write_text(err, encoding="utf-8")
        print(f"[dashboard] error -> wrote fallback HTML at {OUT_HTML}", file=sys.stderr)
        sys.exit(0)
