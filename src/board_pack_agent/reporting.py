from __future__ import annotations

import html
import json
from pathlib import Path

from .charts import write_charts
from .metrics import snapshot_as_prompt_data
from .models import BoardNarrative, MetricRow, MetricSnapshot
from .utils import ensure_dir, money, pct


def write_outputs(
    rows: list[MetricRow],
    snapshot: MetricSnapshot,
    narrative: BoardNarrative,
    company_context: str,
    out_dir: Path,
) -> None:
    ensure_dir(out_dir)
    chart_paths = write_charts(rows, out_dir / "charts")
    write_board_pack(rows, snapshot, narrative, out_dir / "board_pack.md")
    write_investor_update(narrative, out_dir / "investor_update.md")
    write_html_report(snapshot, narrative, chart_paths, out_dir / "board_report.html")
    write_json(rows, snapshot, narrative, company_context, out_dir / "analysis.json")


def write_board_pack(rows: list[MetricRow], snapshot: MetricSnapshot, narrative: BoardNarrative, path: Path) -> None:
    latest = snapshot.latest
    lines = [
        "# Board Pack",
        "",
        f"Latest month: {latest.month}",
        f"Health score: {snapshot.health_score}/100",
        "",
        "## Executive Summary",
        "",
        narrative.executive_summary,
        "",
        "## KPI Snapshot",
        "",
        "| Metric | Latest | Movement |",
        "| --- | ---: | ---: |",
        f"| MRR | {money(latest.mrr)} | {money(snapshot.mrr_growth_abs)} / {pct(snapshot.mrr_growth_pct)} MoM |",
        f"| Churn | {pct(latest.churn_rate)} | {snapshot.churn_delta:+.1f} pts |",
        f"| CAC | {money(latest.cac)} | {pct(snapshot.cac_delta_pct)} MoM |",
        f"| Burn | {money(latest.burn)} | {pct(snapshot.burn_delta_pct)} MoM |",
        f"| Runway | {latest.runway_months:.1f} months | {snapshot.runway_delta:+.1f} months |",
        f"| Activation | {pct(latest.activation_rate)} | {snapshot.activation_delta:+.1f} pts |",
        f"| Pipeline | {money(latest.pipeline)} | {pct(snapshot.pipeline_delta_pct)} MoM |",
        "",
        "## What Changed",
        "",
        *[f"- {item}" for item in narrative.what_changed],
        "",
        "## Risks",
        "",
        *[f"- {item}" for item in narrative.risks],
        "",
        "## Decisions Needed",
        "",
        *[f"- {item}" for item in narrative.decisions_needed],
        "",
        "## Likely Board Questions",
        "",
        *[f"- {item}" for item in narrative.board_questions],
        "",
        "## Recent Metrics",
        "",
        "| Month | MRR | Churn | CAC | Burn | Runway | Activation | Pipeline |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.month} | {money(row.mrr)} | {pct(row.churn_rate)} | {money(row.cac)} | "
            f"{money(row.burn)} | {row.runway_months:.1f} | {pct(row.activation_rate)} | {money(row.pipeline)} |"
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_investor_update(narrative: BoardNarrative, path: Path) -> None:
    content = narrative.investor_update.strip()
    if not content.startswith("#"):
        content = "# Investor Update\n\n" + content
    path.write_text(content + "\n", encoding="utf-8")


def write_html_report(
    snapshot: MetricSnapshot,
    narrative: BoardNarrative,
    chart_paths: dict[str, str],
    path: Path,
) -> None:
    latest = snapshot.latest
    chart_cards = "".join(
        f"""
        <section class="chart-card">
          <img src="{html.escape(Path(chart_path).relative_to(path.parent).as_posix())}" alt="{html.escape(name)} chart">
        </section>
        """
        for name, chart_path in chart_paths.items()
    )
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Board Pack Report</title>
  <style>
    :root {{
      --ink: #172026;
      --muted: #64717c;
      --line: #d9e1e7;
      --bg: #f7f9fb;
      --panel: #ffffff;
      --accent: #0f766e;
      --risk: #b42318;
      --decision: #7c3aed;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
    }}
    header {{
      padding: 38px 32px 22px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: clamp(30px, 5vw, 48px);
      letter-spacing: 0;
    }}
    header p {{
      margin: 0;
      max-width: 920px;
      color: var(--muted);
      font-size: 17px;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 24px auto 48px;
      display: grid;
      gap: 18px;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .card, .chart-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }}
    .kpi-label {{
      color: var(--muted);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .kpi-value {{
      font-size: 28px;
      font-weight: 760;
      margin-top: 6px;
    }}
    .summary {{
      border-left: 5px solid var(--accent);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
      letter-spacing: 0;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li + li {{ margin-top: 8px; }}
    .charts {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    img {{
      display: block;
      max-width: 100%;
      height: auto;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #fbfcfd;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      font: inherit;
    }}
    @media (max-width: 900px) {{
      .kpis, .grid, .charts {{ grid-template-columns: 1fr; }}
      header {{ padding: 28px 18px 18px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Board Pack Report</h1>
    <p>Board-ready operating narrative, risks, decisions, charts, and investor update generated from a metrics CSV.</p>
  </header>
  <main>
    <section class="kpis">
      <div class="card"><div class="kpi-label">MRR</div><div class="kpi-value">{money(latest.mrr)}</div></div>
      <div class="card"><div class="kpi-label">MRR Growth</div><div class="kpi-value">{pct(snapshot.mrr_growth_pct)}</div></div>
      <div class="card"><div class="kpi-label">Runway</div><div class="kpi-value">{latest.runway_months:.1f} mo</div></div>
      <div class="card"><div class="kpi-label">Health Score</div><div class="kpi-value">{snapshot.health_score}/100</div></div>
    </section>
    <section class="card summary">
      <h2>Executive Summary</h2>
      <p>{html.escape(narrative.executive_summary)}</p>
    </section>
    <section class="charts">
      {chart_cards}
    </section>
    <section class="grid">
      <div class="card">
        <h2>What Changed</h2>
        <ul>{_list_items(narrative.what_changed)}</ul>
      </div>
      <div class="card">
        <h2>Risks</h2>
        <ul>{_list_items(narrative.risks)}</ul>
      </div>
      <div class="card">
        <h2>Decisions Needed</h2>
        <ul>{_list_items(narrative.decisions_needed)}</ul>
      </div>
      <div class="card">
        <h2>Likely Board Questions</h2>
        <ul>{_list_items(narrative.board_questions)}</ul>
      </div>
    </section>
    <section class="card">
      <h2>Investor Update Draft</h2>
      <pre>{html.escape(narrative.investor_update)}</pre>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def _list_items(items: list[str]) -> str:
    return "".join(f"<li>{html.escape(item)}</li>" for item in items)


def write_json(
    rows: list[MetricRow],
    snapshot: MetricSnapshot,
    narrative: BoardNarrative,
    company_context: str,
    path: Path,
) -> None:
    payload = {
        "company_context": company_context,
        "metrics": [row.__dict__ for row in rows],
        "analysis": snapshot_as_prompt_data(rows, snapshot),
        "narrative": narrative.as_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

