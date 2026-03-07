from __future__ import annotations

from pathlib import Path

SECTIONS: dict[str, list[str]] = {
    "PERFORMANCE": [
        "equity_curve.png",
        "drawdown_curve.png",
        "rolling_sharpe.png",
        "rolling_expectancy.png",
        "rolling_winrate.png",
    ],
    "RISK": [
        "drawdown_distribution.png",
        "max_dd_duration.png",
        "tail_risk.png",
    ],
    "SIGNAL EDGE": [
        "expectancy_vs_score.png",
        "winrate_vs_score.png",
        "profit_factor_vs_score.png",
        "score_distribution.png",
        "score_calibration_curve.png",
    ],
    "ENTRY": [
        "entry_distance_vs_pnl.png",
        "entry_efficiency.png",
        "entry_vs_midprice.png",
    ],
    "EXECUTION": [
        "entry_delay_vs_pnl.png",
        "latency_vs_pnl.png",
        "slippage_distribution.png",
    ],
    "PROFIT CAPTURE": [
        "pnl_vs_mfe.png",
        "pnl_vs_mae.png",
        "profit_capture_ratio.png",
        "mfe_distribution.png",
        "mae_distribution.png",
    ],
    "REGIME": [
        "expectancy_vs_volatility.png",
        "expectancy_vs_atr.png",
        "expectancy_vs_trend.png",
    ],
    "TIME": [
        "pnl_by_hour.png",
        "pnl_by_weekday.png",
        "expectancy_by_hour.png",
    ],
    "SIZING": [
        "size_vs_pnl.png",
        "leverage_vs_pnl.png",
        "expectancy_vs_size_bucket.png",
    ],
    "STABILITY": [
        "rolling_profit_factor.png",
        "rolling_expectancy_stability.png",
        "edge_decay.png",
    ],
}


def _render_cards(names: list[str], charts_dir: Path) -> str:
    out = []
    for name in names:
        if not (charts_dir / name).exists():
            continue
        title = name.rsplit(".", 1)[0].replace("_", " ").title()
        out.append(
            f'      <article class="card">\n'
            f"        <h3>{title}</h3>\n"
            f'        <img src="charts/{name}" alt="{title}" loading="lazy" />\n'
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

    sections_html = "\n    ".join(_section(title, _render_cards(charts, charts_dir)) for title, charts in SECTIONS.items())

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
    <h1>Professional Quant Research Dashboard</h1>
    {sections_html}
  </body>
</html>
"""

    dashboard_path = root / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    return dashboard_path
