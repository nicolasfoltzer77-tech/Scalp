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
    "profit_capture_distribution.png",
    "mfe_vs_realized_pnl.png",
    "time_to_mfe_distribution.png",
    "time_to_mae_distribution.png",
    "time_to_mfe_vs_pnl.png",
    "entry_efficiency_histogram.png",
    "expectancy_vs_entry_delay.png",
    "expectancy_vs_score_C.png",
    "expectancy_vs_score_S.png",
    "expectancy_vs_score_H.png",
    "signal_flag_expectancy.png",
    "expectancy_by_dec_mode.png",
    "expectancy_by_trigger_type.png",
    "expectancy_vs_score_of.png",
    "expectancy_vs_score_mo.png",
    "expectancy_vs_score_br.png",
    "expectancy_vs_rsi.png",
    "expectancy_vs_adx.png",
    "expectancy_by_regime.png",
    "expectancy_by_entry_reason.png",
    "score_C_distribution.png",
    "score_S_distribution.png",
    "score_H_distribution.png",
    "expectancy_by_signal_component.png",
    "expectancy_by_context.png",
    "size_vs_pnl_scatter.png",
    "size_bucket_expectancy.png",
    "expectancy_surface_C_S.png",
    "time_to_mfe_vs_score_S.png",
]

CSH_DIAGNOSTICS_CHARTS = [
    "score_C_distribution.png",
    "score_S_distribution.png",
    "score_H_distribution.png",
    "expectancy_vs_score_C.png",
    "expectancy_vs_score_S.png",
    "expectancy_vs_score_H.png",
    "expectancy_by_signal_component.png",
    "expectancy_by_context.png",
    "size_vs_pnl_scatter.png",
    "size_bucket_expectancy.png",
    "expectancy_surface_C_S.png",
    "time_to_mfe_vs_score_S.png",
]


def _ordered_chart_names(charts_dir: Path, primary_names: Iterable[str]) -> list[str]:
    available = {p.name for p in charts_dir.glob("*.png")}
    ordered = [name for name in primary_names if name in available]
    extras = sorted(name for name in available if name not in set(primary_names))
    return ordered + extras


def _render_cards(chart_names: list[str]) -> str:
    if not chart_names:
        return '      <p>No charts found in analysis_output/charts</p>'
    return "\n".join(
        (
            f'      <article class="card">\n'
            f"        <h2>{name}</h2>\n"
            f'        <img src="charts/{name}" alt="{name}" loading="lazy" />\n'
            "      </article>"
        )
        for name in chart_names
    )


def generate_dashboard(output_root: str | Path = "analysis_output") -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    charts_dir = root / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    all_charts = _ordered_chart_names(charts_dir, DEFAULT_CHARTS)
    csh_charts = [name for name in CSH_DIAGNOSTICS_CHARTS if name in all_charts]
    core_charts = [name for name in all_charts if name not in set(csh_charts)]

    core_cards = _render_cards(core_charts)
    csh_cards = _render_cards(csh_charts)

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
      .section-title {{
        margin: 30px 0 12px;
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
    <h2 class=\"section-title\">Core Diagnostics</h2>
    <div class=\"grid\">{core_cards}
    </div>
    <h2 class=\"section-title\">C/S/H Diagnostics</h2>
    <div class=\"grid\">{csh_cards}
    </div>
  </body>
</html>
"""

    dashboard_path = root / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path
