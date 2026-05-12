from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import MetricRow, MetricSnapshot
from .utils import money, pct


REQUIRED_COLUMNS = {
    "month",
    "mrr",
    "churn_rate",
    "cac",
    "burn",
    "runway_months",
    "activation_rate",
    "pipeline",
}

DEFAULT_RISK_RULES = {
    "strong_mrr_growth_pct": 10.0,
    "moderate_mrr_growth_pct": 5.0,
    "healthy_churn_rate": 3.5,
    "elevated_churn_rate": 4.0,
    "high_churn_rate": 5.0,
    "healthy_activation_rate": 50.0,
    "low_activation_rate": 50.0,
    "very_low_activation_rate": 40.0,
    "cac_improvement_pct": -5.0,
    "cac_worse_pct": 5.0,
    "healthy_runway_months": 12.0,
    "low_runway_months": 9.0,
    "fundraising_runway_months": 10.0,
    "healthy_pipeline_to_mrr": 3.0,
    "low_pipeline_to_mrr": 2.0,
    "healthy_burn_multiple": 6.0,
    "high_burn_multiple": 10.0,
    "burn_increase_pct": 5.0,
    "activation_decision_rate": 55.0,
}


def load_metrics(path: Path) -> list[MetricRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"Missing required columns in {path}: {', '.join(sorted(missing))}")
        rows = [_row_from_csv(row) for row in reader]
    if len(rows) < 2:
        raise ValueError("Metrics CSV needs at least two months to generate trend commentary.")
    return rows


def load_risk_rules(path: Path | None = None) -> dict[str, float]:
    rules = DEFAULT_RISK_RULES.copy()
    if not path:
        return rules

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Risk config must be a JSON object: {path}")

    unknown_keys = sorted(set(raw) - set(DEFAULT_RISK_RULES))
    if unknown_keys:
        raise ValueError(f"Unknown risk config keys in {path}: {', '.join(unknown_keys)}")

    for key, value in raw.items():
        if not isinstance(value, (int, float)):
            raise ValueError(f"Risk config value for {key} must be a number.")
        rules[key] = float(value)
    return rules


def _row_from_csv(row: dict[str, str]) -> MetricRow:
    return MetricRow(
        month=(row.get("month") or "").strip(),
        mrr=_float(row.get("mrr")),
        churn_rate=_float(row.get("churn_rate")),
        cac=_float(row.get("cac")),
        burn=_float(row.get("burn")),
        runway_months=_float(row.get("runway_months")),
        activation_rate=_float(row.get("activation_rate")),
        pipeline=_float(row.get("pipeline")),
        notes=(row.get("notes") or "").strip(),
    )


def _float(value: str | None) -> float:
    if value is None:
        return 0.0
    cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
    if not cleaned:
        return 0.0
    return float(cleaned)


def analyze_metrics(rows: list[MetricRow], risk_rules: dict[str, float] | None = None) -> MetricSnapshot:
    rules = DEFAULT_RISK_RULES.copy()
    if risk_rules:
        rules.update(risk_rules)

    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    mrr_growth_abs = latest.mrr - previous.mrr if previous else 0.0
    mrr_growth_pct = _pct_change(latest.mrr, previous.mrr if previous else 0.0)
    churn_delta = latest.churn_rate - (previous.churn_rate if previous else latest.churn_rate)
    cac_delta_pct = _pct_change(latest.cac, previous.cac if previous else 0.0)
    burn_delta_pct = _pct_change(latest.burn, previous.burn if previous else 0.0)
    runway_delta = latest.runway_months - (previous.runway_months if previous else latest.runway_months)
    activation_delta = latest.activation_rate - (previous.activation_rate if previous else latest.activation_rate)
    pipeline_delta_pct = _pct_change(latest.pipeline, previous.pipeline if previous else 0.0)

    growth_rates = []
    for index in range(1, len(rows)):
        growth_rates.append(_pct_change(rows[index].mrr, rows[index - 1].mrr))
    avg_mrr_growth_pct = sum(growth_rates) / len(growth_rates)
    avg_burn = sum(row.burn for row in rows[-3:]) / min(3, len(rows))
    burn_multiple = latest.burn / mrr_growth_abs if mrr_growth_abs > 0 else None
    pipeline_to_mrr = latest.pipeline / latest.mrr if latest.mrr else 0.0

    health_score = _score_health(
        mrr_growth_pct=mrr_growth_pct,
        churn_rate=latest.churn_rate,
        cac_delta_pct=cac_delta_pct,
        runway_months=latest.runway_months,
        activation_rate=latest.activation_rate,
        pipeline_to_mrr=pipeline_to_mrr,
        burn_multiple=burn_multiple,
        risk_rules=rules,
    )

    snapshot = MetricSnapshot(
        latest=latest,
        previous=previous,
        mrr_growth_pct=mrr_growth_pct,
        mrr_growth_abs=mrr_growth_abs,
        churn_delta=churn_delta,
        cac_delta_pct=cac_delta_pct,
        burn_delta_pct=burn_delta_pct,
        runway_delta=runway_delta,
        activation_delta=activation_delta,
        pipeline_delta_pct=pipeline_delta_pct,
        avg_mrr_growth_pct=avg_mrr_growth_pct,
        avg_burn=avg_burn,
        burn_multiple=burn_multiple,
        pipeline_to_mrr=pipeline_to_mrr,
        health_score=health_score,
    )
    snapshot.highlights = _build_highlights(snapshot)
    snapshot.risks = _build_risks(snapshot, rules)
    snapshot.decisions = _build_decisions(snapshot, rules)
    return snapshot


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100


def _score_health(
    mrr_growth_pct: float,
    churn_rate: float,
    cac_delta_pct: float,
    runway_months: float,
    activation_rate: float,
    pipeline_to_mrr: float,
    burn_multiple: float | None,
    risk_rules: dict[str, float],
) -> int:
    score = 50
    if mrr_growth_pct >= risk_rules["strong_mrr_growth_pct"]:
        score += 15
    elif mrr_growth_pct >= risk_rules["moderate_mrr_growth_pct"]:
        score += 8
    else:
        score -= 8

    if churn_rate <= risk_rules["healthy_churn_rate"]:
        score += 10
    elif churn_rate >= risk_rules["high_churn_rate"]:
        score -= 12

    if activation_rate >= risk_rules["healthy_activation_rate"]:
        score += 10
    elif activation_rate < risk_rules["very_low_activation_rate"]:
        score -= 8

    if cac_delta_pct <= risk_rules["cac_improvement_pct"]:
        score += 8
    elif cac_delta_pct > risk_rules["cac_worse_pct"]:
        score -= 8

    if runway_months >= risk_rules["healthy_runway_months"]:
        score += 8
    elif runway_months < risk_rules["low_runway_months"]:
        score -= 12

    if pipeline_to_mrr >= risk_rules["healthy_pipeline_to_mrr"]:
        score += 8
    elif pipeline_to_mrr < risk_rules["low_pipeline_to_mrr"]:
        score -= 8

    if burn_multiple is not None:
        if burn_multiple <= risk_rules["healthy_burn_multiple"]:
            score += 8
        elif burn_multiple > risk_rules["high_burn_multiple"]:
            score -= 10
    return max(0, min(100, score))


def _build_highlights(snapshot: MetricSnapshot) -> list[str]:
    latest = snapshot.latest
    highlights = [
        f"MRR reached {money(latest.mrr)}, up {pct(snapshot.mrr_growth_pct)} month over month.",
        f"Pipeline reached {money(latest.pipeline)}, up {pct(snapshot.pipeline_delta_pct)} month over month.",
    ]
    if snapshot.activation_delta > 0:
        highlights.append(f"Activation improved by {snapshot.activation_delta:.1f} points to {pct(latest.activation_rate)}.")
    if snapshot.churn_delta < 0:
        highlights.append(f"Churn improved by {abs(snapshot.churn_delta):.1f} points to {pct(latest.churn_rate)}.")
    if snapshot.cac_delta_pct < 0:
        highlights.append(f"CAC decreased {pct(abs(snapshot.cac_delta_pct))} to {money(latest.cac)}.")
    return highlights


def _format_rule_value(value: float) -> str:
    return f"{value:g}"


def _build_risks(snapshot: MetricSnapshot, risk_rules: dict[str, float]) -> list[str]:
    latest = snapshot.latest
    risks: list[str] = []
    if latest.runway_months < risk_rules["low_runway_months"]:
        threshold = _format_rule_value(risk_rules["low_runway_months"])
        risks.append(f"Runway is below {threshold} months at {latest.runway_months:.1f} months, which compresses fundraising options.")
    elif latest.runway_months < risk_rules["healthy_runway_months"]:
        risks.append(f"Runway is {latest.runway_months:.1f} months, so the company should manage burn before the next raise.")
    if snapshot.burn_delta_pct > risk_rules["burn_increase_pct"]:
        risks.append(f"Burn increased {pct(snapshot.burn_delta_pct)} month over month; growth quality needs to justify the spend.")
    if latest.churn_rate > risk_rules["elevated_churn_rate"]:
        risks.append(f"Churn is still elevated at {pct(latest.churn_rate)}, especially if expansion is not offsetting it.")
    if latest.activation_rate < risk_rules["low_activation_rate"]:
        threshold = _format_rule_value(risk_rules["low_activation_rate"])
        risks.append(f"Activation is below {threshold} percent, which can leak revenue before customers reach value.")
    if snapshot.pipeline_to_mrr < risk_rules["low_pipeline_to_mrr"]:
        risks.append(f"Pipeline is only {snapshot.pipeline_to_mrr:.1f}x current MRR, leaving limited room for target misses.")
    if not risks:
        risks.append("No single metric is flashing red, but burn discipline and activation quality should stay visible.")
    return risks


def _build_decisions(snapshot: MetricSnapshot, risk_rules: dict[str, float]) -> list[str]:
    latest = snapshot.latest
    decisions: list[str] = []
    if latest.runway_months < risk_rules["fundraising_runway_months"]:
        decisions.append("Decide whether to reduce discretionary burn or start fundraising prep earlier.")
    if latest.churn_rate > risk_rules["healthy_churn_rate"]:
        decisions.append("Decide which customer segment or onboarding gap is driving churn and assign an owner.")
    if latest.activation_rate < risk_rules["activation_decision_rate"]:
        decisions.append("Decide whether activation improvement is the top product/GTM priority for the next month.")
    if snapshot.pipeline_to_mrr >= risk_rules["healthy_pipeline_to_mrr"]:
        decisions.append("Decide which pipeline segments deserve founder time before adding more top-of-funnel volume.")
    if snapshot.cac_delta_pct < 0 and snapshot.mrr_growth_pct > risk_rules["moderate_mrr_growth_pct"]:
        decisions.append("Decide whether CAC improvement is strong enough to increase spend in the best-performing channel.")
    if not decisions:
        decisions.append("Decide the one operating constraint the next board cycle should optimize around.")
    return decisions


def snapshot_as_prompt_data(rows: list[MetricRow], snapshot: MetricSnapshot) -> dict:
    return {
        "latest_month": snapshot.latest.month,
        "health_score": snapshot.health_score,
        "latest_metrics": snapshot.latest.__dict__,
        "computed_metrics": {
            "mrr_growth_pct": snapshot.mrr_growth_pct,
            "mrr_growth_abs": snapshot.mrr_growth_abs,
            "churn_delta": snapshot.churn_delta,
            "cac_delta_pct": snapshot.cac_delta_pct,
            "burn_delta_pct": snapshot.burn_delta_pct,
            "runway_delta": snapshot.runway_delta,
            "activation_delta": snapshot.activation_delta,
            "pipeline_delta_pct": snapshot.pipeline_delta_pct,
            "avg_mrr_growth_pct": snapshot.avg_mrr_growth_pct,
            "avg_burn": snapshot.avg_burn,
            "burn_multiple": snapshot.burn_multiple,
            "pipeline_to_mrr": snapshot.pipeline_to_mrr,
        },
        "deterministic_highlights": snapshot.highlights,
        "deterministic_risks": snapshot.risks,
        "deterministic_decisions": snapshot.decisions,
        "recent_rows": [row.__dict__ for row in rows[-6:]],
    }

