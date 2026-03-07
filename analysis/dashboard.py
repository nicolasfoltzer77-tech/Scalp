from __future__ import annotations

from pathlib import Path

SECTIONS: dict[str, list[str]] = {
    "Performance": [
        "equity_curve.png",
        "drawdown_curve.png",
        "rolling_sharpe.png",
        "rolling_expectancy.png",
        "rolling_winrate.png",
    ],
    "Risk": [
        "drawdown_distribution.png",
        "max_dd_duration.png",
        "tail_risk.png",
    ],
    "Signal Edge": [
        "expectancy_vs_score.png",
        "winrate_vs_score.png",
        "profit_factor_vs_score.png",
        "score_distribution.png",
        "score_calibration_curve.png",
    ],
    "Entry": [
        "entry_distance_vs_pnl.png",
        "entry_efficiency.png",
        "entry_vs_midprice.png",
    ],
    "Execution": [
        "entry_delay_vs_pnl.png",
        "latency_vs_pnl.png",
        "slippage_distribution.png",
    ],
    "Profit Capture": [
        "pnl_vs_mfe.png",
        "pnl_vs_mae.png",
        "profit_capture_ratio.png",
        "mfe_distribution.png",
        "mae_distribution.png",
    ],
    "Regime": [
        "expectancy_vs_volatility.png",
        "expectancy_vs_atr.png",
        "expectancy_vs_trend.png",
    ],
    "Time": [
        "pnl_by_hour.png",
        "pnl_by_weekday.png",
        "expectancy_by_hour.png",
    ],
    "Sizing": [
        "size_vs_pnl.png",
        "leverage_vs_pnl.png",
        "expectancy_vs_size_bucket.png",
    ],
    "Stability": [
        "rolling_profit_factor.png",
        "rolling_expectancy.png",
        "edge_decay.png",
    ],
}


def _card(name: str) -> str:
    return (
        f'      <article class="card">\n'
        f"        <h3>{name}</h3>\n"
        f'        <img src="graphs/{name}" alt="{name}" loading="lazy" />\n'
        "      </article>"
    )


def _render_section(title: str, filenames: list[str], available: set[str]) -> str:
    cards = [_card(n) for n in filenames if n in available]
    body = "\n".join(cards) if cards else "      <p>No charts available.</p>"
    return f'<h2 class="section-title">{title}</h2>\n    <div class="grid">{body}\n    </div>'


def generate_dashboard(output_root: str | Path = "analysis_output") -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    graphs_dir = root / "graphs"
    charts_dir = root / "charts"
    source_dir = graphs_dir if graphs_dir.exists() else charts_dir
    source_dir.mkdir(parents=True, exist_ok=True)

    available = {p.name for p in source_dir.glob("*.png")}
    rendered = [_render_section(title, names, available) for title, names in SECTIONS.items()]

    categorized = {name for names in SECTIONS.values() for name in names}
    extras = sorted(available - categorized)
    if extras:
        rendered.append(_render_section("Additional Graphs", extras, available))

    html = f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Quant Research Dashboard</title>
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
    <h1>Professional Quant Research Dashboard</h1>
    {'\n    '.join(rendered)}
  </body>
</html>
"""

    dashboard_path = root / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path
