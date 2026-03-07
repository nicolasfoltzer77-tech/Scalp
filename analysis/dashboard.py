from __future__ import annotations

from pathlib import Path

ENTRY_QUALITY_CHARTS = [
    "expectancy_vs_entry_distance.png",
    "expectancy_vs_range_pos.png",
    "mfe_vs_score_C.png",
]

SIGNAL_QUALITY_CHARTS = [
    "trigger_strength_vs_pnl.png",
    "signal_age_vs_pnl.png",
]

EXECUTION_QUALITY_CHARTS = [
    "entry_delay_vs_pnl.png",
    "expectancy_vs_entry_delay.png",
]

PROFIT_CAPTURE_CHARTS = [
    "profit_capture_distribution.png",
    "pnl_vs_mfe.png",
    "pnl_vs_mae.png",
]


def _render_cards(names: list[str], charts_dir: Path) -> str:
    out = []
    for name in names:
        if not (charts_dir / name).exists():
            continue
        out.append(
            f'      <article class="card">\n'
            f"        <h3>{name}</h3>\n"
            f'        <img src="charts/{name}" alt="{name}" loading="lazy" />\n'
            "      </article>"
        )
    return "\n".join(out) if out else "      <p>No charts available.</p>"


def _section(title: str, cards: str) -> str:
    return f'<h2 class="section-title">{title}</h2>\n    <div class="grid">{cards}\n    </div>'


def generate_dashboard(output_root: str | Path = "analysis_output") -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    charts_dir = root / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    html = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Analysis Dashboard</title>
    <style>
      body {{ font-family: Inter, Arial, sans-serif; margin: 0; padding: 24px; background: #f5f7fa; color: #1f2937; }}
      .section-title {{ margin: 28px 0 10px; }}
      .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }}
      .card {{ background: white; border-radius: 10px; padding: 12px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }}
      .card img {{ width: 100%; height: auto; display: block; }}
      .card h3 {{ margin: 0 0 10px; font-size: 0.95rem; word-break: break-word; }}
    </style>
  </head>
  <body>
    <h1>Trading Bot Analysis Dashboard</h1>
    {_section('ENTRY QUALITY', _render_cards(ENTRY_QUALITY_CHARTS, charts_dir))}
    {_section('SIGNAL QUALITY', _render_cards(SIGNAL_QUALITY_CHARTS, charts_dir))}
    {_section('EXECUTION QUALITY', _render_cards(EXECUTION_QUALITY_CHARTS, charts_dir))}
    {_section('PROFIT CAPTURE', _render_cards(PROFIT_CAPTURE_CHARTS, charts_dir))}
  </body>
</html>
"""

    dashboard_path = root / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path
