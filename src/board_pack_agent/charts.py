from __future__ import annotations

from pathlib import Path

from .models import MetricRow
from .utils import ensure_dir, money, pct


def write_charts(rows: list[MetricRow], out_dir: Path) -> dict[str, str]:
    ensure_dir(out_dir)
    charts = {
        "mrr": out_dir / "mrr.svg",
        "runway": out_dir / "runway.svg",
        "activation": out_dir / "activation.svg",
        "pipeline": out_dir / "pipeline.svg",
    }
    _write_line_chart(charts["mrr"], rows, "MRR", lambda row: row.mrr, money, "#0f766e")
    _write_line_chart(charts["runway"], rows, "Runway Months", lambda row: row.runway_months, lambda value: f"{value:.1f} mo", "#7c3aed")
    _write_line_chart(charts["activation"], rows, "Activation Rate", lambda row: row.activation_rate, pct, "#2563eb")
    _write_line_chart(charts["pipeline"], rows, "Pipeline", lambda row: row.pipeline, money, "#c2410c")
    return {key: str(path) for key, path in charts.items()}


def _write_line_chart(
    path: Path,
    rows: list[MetricRow],
    title: str,
    value_getter,
    value_formatter,
    color: str,
) -> None:
    width = 760
    height = 360
    margin_left = 72
    margin_right = 28
    margin_top = 54
    margin_bottom = 62
    values = [float(value_getter(row)) for row in rows]
    labels = [row.month for row in rows]
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        min_value = min_value * 0.9
        max_value = max_value * 1.1 if max_value else 1
    padding = (max_value - min_value) * 0.12
    y_min = min_value - padding
    y_max = max_value + padding

    points = []
    for index, value in enumerate(values):
        x = margin_left + (index / max(1, len(values) - 1)) * (width - margin_left - margin_right)
        y = margin_top + ((y_max - value) / (y_max - y_min)) * (height - margin_top - margin_bottom)
        points.append((x, y))

    line_path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    y_ticks = [y_min + (y_max - y_min) * step / 4 for step in range(5)]

    tick_lines = []
    for tick in y_ticks:
        y = margin_top + ((y_max - tick) / (y_max - y_min)) * (height - margin_top - margin_bottom)
        tick_lines.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" stroke="#e5e7eb" />'
            f'<text x="{margin_left - 10}" y="{y + 4:.1f}" text-anchor="end" fill="#64748b" font-size="12">{value_formatter(tick)}</text>'
        )

    x_labels = []
    for index, label in enumerate(labels):
        x, _ = points[index]
        x_labels.append(
            f'<text x="{x:.1f}" y="{height - 24}" text-anchor="middle" fill="#64748b" font-size="12">{label}</text>'
        )

    circles = []
    for index, (x, y) in enumerate(points):
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ffffff" stroke="{color}" stroke-width="3">'
            f"<title>{labels[index]}: {value_formatter(values[index])}</title></circle>"
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title} chart">
  <rect width="100%" height="100%" fill="#ffffff" rx="8" />
  <text x="{margin_left}" y="32" fill="#172026" font-size="22" font-family="Inter, system-ui, sans-serif" font-weight="700">{title}</text>
  <text x="{width - margin_right}" y="32" fill="{color}" font-size="16" font-family="Inter, system-ui, sans-serif" text-anchor="end">{value_formatter(values[-1])}</text>
  {''.join(tick_lines)}
  <polyline fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="{line_path}" />
  {''.join(circles)}
  {''.join(x_labels)}
</svg>
"""
    path.write_text(svg, encoding="utf-8")

