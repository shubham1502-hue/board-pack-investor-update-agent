from __future__ import annotations

from pathlib import Path

from .llm import LLMProvider
from .metrics import analyze_metrics, load_metrics, load_risk_rules
from .models import BoardNarrative, MetricRow, MetricSnapshot


def load_context(path: Path | None) -> str:
    if not path:
        return (
            "Early-stage startup preparing a board pack and investor update. "
            "The goal is to explain what changed, where risk is increasing, and what decisions need founder attention."
        )
    return path.read_text(encoding="utf-8")


def run_analysis(
    metrics_path: Path,
    context_path: Path | None,
    provider: LLMProvider,
    risk_config_path: Path | None = None,
) -> tuple[list[MetricRow], MetricSnapshot, BoardNarrative, str]:
    rows = load_metrics(metrics_path)
    risk_rules = load_risk_rules(risk_config_path)
    snapshot = analyze_metrics(rows, risk_rules)
    context = load_context(context_path)
    narrative = provider.synthesize(rows, snapshot, context)
    return rows, snapshot, narrative, context

