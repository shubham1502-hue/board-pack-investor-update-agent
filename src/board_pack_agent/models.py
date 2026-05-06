from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MetricRow:
    month: str
    mrr: float
    churn_rate: float
    cac: float
    burn: float
    runway_months: float
    activation_rate: float
    pipeline: float
    notes: str = ""


@dataclass
class MetricSnapshot:
    latest: MetricRow
    previous: MetricRow | None
    mrr_growth_pct: float
    mrr_growth_abs: float
    churn_delta: float
    cac_delta_pct: float
    burn_delta_pct: float
    runway_delta: float
    activation_delta: float
    pipeline_delta_pct: float
    avg_mrr_growth_pct: float
    avg_burn: float
    burn_multiple: float | None
    pipeline_to_mrr: float
    health_score: int
    highlights: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)


@dataclass
class BoardNarrative:
    executive_summary: str
    what_changed: list[str]
    risks: list[str]
    decisions_needed: list[str]
    board_questions: list[str]
    investor_update: str
    raw_model_output: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "executive_summary": self.executive_summary,
            "what_changed": self.what_changed,
            "risks": self.risks,
            "decisions_needed": self.decisions_needed,
            "board_questions": self.board_questions,
            "investor_update": self.investor_update,
        }

