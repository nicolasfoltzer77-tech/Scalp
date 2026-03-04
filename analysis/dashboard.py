from __future__ import annotations

from pathlib import Path
from typing import Iterable

DEFAULT_CHARTS = [
    "equity_curve.png",
    "drawdown_curve.png",
    "expectancy_vs_leverage.png",
    "expectancy_vs_atr.png",
    "expectancy_vs_duration.png",
    "signal_expectancy_bar.png",
    "pyramiding_edge.png",
    "pnl_by_close_reason.png",
    "pyramiding_expectancy.png",
    "mfe_mae_scatter.png",
    "mfe_distribution.png",
    "mae_distribution.png",
    "entry_efficiency_hist.png",
    "entry_efficiency_vs_pnl.png",
    "expectancy_vs_range.png",
]


def _ordered_chart_names(charts_dir: Path, primary_names: Iterable[str]) -> list[str]:
    available = {p.name for p in charts_dir.glob("*.png")}
    ordered = [name for name in primary_names if name in available]
    extras = sorted(name for name in available if name not in set(primary_names))
    return ordered + extras


def generate_dashboard(output_root: str | Path = "analysis_output") -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    charts_dir = root / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_names = _ordered_chart_names(charts_dir, DEFAULT_CHARTS)

    cards = "\n".join(
        (
            f'      <article class="card">\n'
            f"        <h2>{name}</h2>\n"
            f'        <img src="charts/{name}" alt="{name}" loading="lazy" />\n'
            "      </article>"
        )
        for name in chart_names
    )

    html = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Analysis Dashboard</title>
    <style>
      :root {{
        color-scheme: light dark;
      }}
      body {{
        font-family: Inter, Arial, sans-serif;
        margin: 0;
        padding: 24px;
        background: #f5f7fa;
        color: #1f2937;
      }}
      h1 {{
        margin-top: 0;
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
      }}
      .card {{
        background: white;
        border-radius: 12px;
        padding: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      }}
      .card h2 {{
        margin: 0 0 10px;
        font-size: 1rem;
        word-break: break-word;
      }}
      .card img {{
        width: 100%;
        height: auto;
        display: block;
      }}
    </style>
  </head>
  <body>
    <h1>Trading Bot Analysis Dashboard</h1>
    <div class=\"grid\">
{cards if cards else '      <p>No charts found in analysis_output/charts</p>'}
    </div>
  </body>
</html>
"""

    dashboard_path = root / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path
