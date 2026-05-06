from __future__ import annotations

import json

from .metrics import snapshot_as_prompt_data
from .models import MetricRow, MetricSnapshot


SYSTEM_PROMPT = """You are a founder's office operator preparing a board pack and investor update.
Your job is to turn metrics into a concise, board-ready operating narrative.

Rules:
- Do not invent facts not present in the metrics or company context.
- Use direct, founder-level language.
- Focus on what changed, why it matters, risks, and decisions needed.
- Keep the investor update clear enough to send after light human editing.
- Return valid JSON only.
"""


def build_board_prompt(rows: list[MetricRow], snapshot: MetricSnapshot, company_context: str) -> str:
    payload = {
        "company_context": company_context,
        "metrics_analysis": snapshot_as_prompt_data(rows, snapshot),
    }
    schema = {
        "executive_summary": "one board-ready paragraph",
        "what_changed": ["4-6 concise bullets"],
        "risks": ["3-5 concise bullets"],
        "decisions_needed": ["3-5 decisions for founders/board"],
        "board_questions": ["3-5 likely board questions"],
        "investor_update": "sendable monthly investor update with sections: Opening, What improved, What is risky, Where we need help, Closing",
    }
    return (
        "Prepare the board narrative and investor update from this data.\n\n"
        f"INPUT:\n{json.dumps(payload, indent=2)}\n\n"
        f"OUTPUT_SCHEMA:\n{json.dumps(schema, indent=2)}"
    )

