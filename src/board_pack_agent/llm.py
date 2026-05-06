from __future__ import annotations

import json
import os
import re
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from .metrics import snapshot_as_prompt_data
from .models import BoardNarrative, MetricRow, MetricSnapshot
from .prompts import SYSTEM_PROMPT, build_board_prompt
from .utils import money, pct


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def synthesize(self, rows: list[MetricRow], snapshot: MetricSnapshot, company_context: str) -> BoardNarrative:
        raise NotImplementedError


def extract_json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"```$", "", value).strip()
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class MockProvider(LLMProvider):
    def synthesize(self, rows: list[MetricRow], snapshot: MetricSnapshot, company_context: str) -> BoardNarrative:
        latest = snapshot.latest
        executive_summary = (
            f"{latest.month} was a stronger growth month, with MRR at {money(latest.mrr)} "
            f"and month-over-month growth of {pct(snapshot.mrr_growth_pct)}. "
            f"Activation improved to {pct(latest.activation_rate)} and churn moved to {pct(latest.churn_rate)}, "
            f"but runway is now {latest.runway_months:.1f} months, so the board discussion should stay focused "
            "on growth quality, burn discipline, and which pipeline segments deserve founder time."
        )
        what_changed = [
            *snapshot.highlights[:5],
            f"Health score is {snapshot.health_score}/100 based on growth, churn, activation, CAC, runway, and pipeline coverage.",
        ]
        risks = snapshot.risks[:5]
        decisions = snapshot.decisions[:5]
        board_questions = [
            "Which customer segment is producing the highest-quality MRR growth?",
            "Is activation improvement durable or driven by a one-time onboarding push?",
            "What burn level gives us the best fundraising position three months from now?",
            "Which pipeline deals need founder involvement this month?",
        ]
        investor_update = (
            f"Hi everyone,\n\n"
            f"Quick monthly update for {latest.month}. MRR reached {money(latest.mrr)}, up {pct(snapshot.mrr_growth_pct)} month over month. "
            f"Activation improved to {pct(latest.activation_rate)}, pipeline reached {money(latest.pipeline)}, "
            f"and CAC moved {pct(snapshot.cac_delta_pct)} versus last month.\n\n"
            "What improved:\n"
            + "\n".join(f"- {item}" for item in snapshot.highlights[:4])
            + "\n\nWhat we are watching:\n"
            + "\n".join(f"- {item}" for item in risks[:3])
            + "\n\nWhere help would be useful:\n"
            "- Warm intros to AI SaaS buyers who care about support, success, or internal knowledge workflows.\n"
            "- Feedback on whether we should prioritize enterprise expansion or faster mid-market acquisition this month.\n\n"
            "Thanks,\n"
            "[Founder]"
        )
        return BoardNarrative(
            executive_summary=executive_summary,
            what_changed=what_changed,
            risks=risks,
            decisions_needed=decisions,
            board_questions=board_questions,
            investor_update=investor_update,
            raw_model_output={"provider": "mock", "prompt_data": snapshot_as_prompt_data(rows, snapshot)},
        )


class GeminiProvider(LLMProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set.")

    def synthesize(self, rows: list[MetricRow], snapshot: MetricSnapshot, company_context: str) -> BoardNarrative:
        try:
            from google import genai  # type: ignore
        except ImportError as exc:
            raise LLMError("Install Gemini support with: pip install -e '.[gemini]'") from exc

        client = genai.Client(api_key=self.api_key)
        prompt = build_board_prompt(rows, snapshot, company_context)
        response = client.models.generate_content(
            model=self.model,
            contents=f"{SYSTEM_PROMPT}\n\n{prompt}",
            config={"response_mime_type": "application/json"},
        )
        return narrative_from_raw(extract_json_object(response.text or "{}"))


class GroqProvider(LLMProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not set.")

    def synthesize(self, rows: list[MetricRow], snapshot: MetricSnapshot, company_context: str) -> BoardNarrative:
        prompt = build_board_prompt(rows, snapshot, company_context)
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Groq request failed: {exc}") from exc
        return narrative_from_raw(extract_json_object(data["choices"][0]["message"]["content"]))


def narrative_from_raw(raw: dict[str, Any]) -> BoardNarrative:
    def as_list(key: str) -> list[str]:
        value = raw.get(key)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    return BoardNarrative(
        executive_summary=str(raw.get("executive_summary") or "").strip(),
        what_changed=as_list("what_changed"),
        risks=as_list("risks"),
        decisions_needed=as_list("decisions_needed"),
        board_questions=as_list("board_questions"),
        investor_update=str(raw.get("investor_update") or "").strip(),
        raw_model_output=raw,
    )


def get_provider(name: str) -> LLMProvider:
    normalized = name.lower().strip()
    if normalized == "mock":
        return MockProvider()
    if normalized == "gemini":
        return GeminiProvider()
    if normalized == "groq":
        return GroqProvider()
    raise ValueError(f"Unknown provider: {name}. Use mock, gemini, or groq.")

