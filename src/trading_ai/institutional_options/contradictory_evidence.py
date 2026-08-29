from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .domain import InstitutionalOpportunity, OpportunityThesis, ThesisDirection


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ContradictoryEvidenceAuthority:
    dominant_direction: str
    state: str
    severity_score: float
    execution_blocked: bool
    allow_opposite_conditional: bool
    opposite_direction: str
    reason_codes: tuple[str, ...]
    evidence: tuple[str, ...]
    policy_version: str = "M68.2.1.15.5-CONTRADICTORY-EVIDENCE-1.0"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reason_codes"] = list(self.reason_codes)
        payload["evidence"] = list(self.evidence)
        return payload


def assess_contradictory_evidence(
    opportunity: InstitutionalOpportunity,
    thesis: OpportunityThesis,
) -> ContradictoryEvidenceAuthority:
    dominant = thesis.direction.value
    opposite = "BEARISH" if dominant == "BULLISH" else "BULLISH"
    score = 0.0
    reasons: list[str] = []
    evidence: list[str] = []

    inflection = dict(opportunity.inflection_intelligence or {})
    transition = str(inflection.get("transition_state") or "").upper()
    inflection_direction = str(inflection.get("direction") or "").upper()
    inflection_score = _number(inflection.get("inflection_score"))
    acceleration = _number(inflection.get("acceleration"))

    if transition == "TREND_EXHAUSTION":
        score += 35.0
        reasons.append("TREND_EXHAUSTION")
        evidence.append(f"Inflection transition {transition}; score {inflection_score:.1f}")
    if dominant == "BULLISH" and transition == "EARLY_BREAKDOWN":
        score += 55.0
        reasons.append("EARLY_BREAKDOWN")
    elif dominant == "BEARISH" and transition == "EARLY_BREAKOUT":
        score += 55.0
        reasons.append("EARLY_BREAKOUT")
    if inflection_direction and inflection_direction == opposite:
        score += 25.0
        reasons.append("INFLECTION_DIRECTION_OPPOSES_THESIS")
    if dominant == "BULLISH" and acceleration < -1.0:
        score += min(15.0, abs(acceleration) * 4.0)
        reasons.append("NEGATIVE_INFLECTION_ACCELERATION")
    elif dominant == "BEARISH" and acceleration > 1.0:
        score += min(15.0, abs(acceleration) * 4.0)
        reasons.append("POSITIVE_INFLECTION_ACCELERATION")

    metadata = dict(opportunity.metadata or {})
    forecast = dict(metadata.get("forecast_evidence") or {})
    conflict_codes = tuple(str(x) for x in forecast.get("conflict_codes") or ())
    if conflict_codes or forecast.get("directional_consistency") is False:
        score += 30.0
        reasons.append("FORECAST_SEMANTIC_CONFLICT")
        evidence.append("Forecast contains unresolved directional/return contradiction")
    forecast_direction = str(forecast.get("forecast_direction") or "").upper()
    if forecast_direction == opposite:
        score += 20.0
        reasons.append("FORECAST_OPPOSES_THESIS")

    volume = dict(metadata.get("institutional_volume") or {})
    accumulation = _number(volume.get("accumulation_score") or volume.get("accumulation_distribution_score"), 50.0)
    distribution = _number(volume.get("distribution_score") or volume.get("distribution_risk_score"), 50.0)
    signal = str(volume.get("signal") or "").upper()
    if dominant == "BULLISH" and (distribution >= accumulation + 8.0 or "DISTRIBUT" in signal):
        score += 18.0
        reasons.append("DISTRIBUTION_EXCEEDS_ACCUMULATION")
        evidence.append(f"Distribution {distribution:.1f} versus accumulation {accumulation:.1f}")
    elif dominant == "BEARISH" and (accumulation >= distribution + 8.0 or "ACCUMUL" in signal):
        score += 18.0
        reasons.append("ACCUMULATION_EXCEEDS_DISTRIBUTION")

    score = round(min(100.0, score), 4)
    if score >= 55.0:
        state = "REVERSAL_WATCH"
        execution_blocked = True
        allow_opposite_conditional = True
    elif score >= 30.0:
        state = f"{dominant}_DETERIORATING"
        execution_blocked = False
        allow_opposite_conditional = True
    else:
        state = f"{dominant}_CONTINUATION"
        execution_blocked = False
        allow_opposite_conditional = False

    return ContradictoryEvidenceAuthority(
        dominant_direction=dominant,
        state=state,
        severity_score=score,
        execution_blocked=execution_blocked,
        allow_opposite_conditional=allow_opposite_conditional,
        opposite_direction=opposite,
        reason_codes=tuple(dict.fromkeys(reasons)),
        evidence=tuple(evidence),
    )
