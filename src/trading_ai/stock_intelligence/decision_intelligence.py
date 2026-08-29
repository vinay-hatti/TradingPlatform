from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, log, sqrt
from typing import Any

from .profile import StockIntelligenceProfile, stable_hash


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def _logit(probability: float) -> float:
    p = max(0.01, min(0.99, probability))
    return log(p / (1.0 - p))


@dataclass
class BarrierProbabilityAssessment:
    target_1_before_stop: float = 0.0
    target_2_before_stop: float = 0.0
    target_3_before_stop: float = 0.0
    expected_mfe_pct: float = 0.0
    expected_mae_pct: float = 0.0
    expected_holding_days: int = 0
    model: str = "DETERMINISTIC_GEOMETRY_PRIOR"
    calibration_status: str = "UNCALIBRATED"
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class InstitutionalDecisionAssessment:
    version: str = "M76.2-IDI-1.0"
    overall_trade_quality: float = 0.0
    decision_readiness: float = 0.0
    capital_priority: float = 0.0
    opportunity_freshness: float = 0.0
    institutional_grade: str = "C"
    decision: str = "WATCH"
    opportunity_lifecycle: str = "DISCOVERED"
    quality_vector: dict[str, float] = field(default_factory=dict)
    barrier_probability: BarrierProbabilityAssessment = field(default_factory=BarrierProbabilityAssessment)
    explainability: dict[str, Any] = field(default_factory=dict)
    evidence_registry: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    competition: dict[str, Any] = field(default_factory=dict)
    learning_snapshot: dict[str, Any] = field(default_factory=dict)
    outcome_probability: dict[str, Any] = field(default_factory=dict)
    passport_id: str = ""
    state_hash: str = ""

    def finalize(self) -> "InstitutionalDecisionAssessment":
        payload = {
            "version": self.version,
            "overall_trade_quality": self.overall_trade_quality,
            "decision_readiness": self.decision_readiness,
            "capital_priority": self.capital_priority,
            "opportunity_freshness": self.opportunity_freshness,
            "institutional_grade": self.institutional_grade,
            "decision": self.decision,
            "opportunity_lifecycle": self.opportunity_lifecycle,
            "quality_vector": self.quality_vector,
            "barrier_probability": self.barrier_probability.__dict__,
            "explainability": self.explainability,
            "evidence_registry": self.evidence_registry,
            "warnings": self.warnings,
            "competition": self.competition,
            "learning_snapshot": self.learning_snapshot,
        }
        self.state_hash = stable_hash(payload)
        self.passport_id = f"IDI-{self.state_hash[:16].upper()}"
        return self


class InstitutionalDecisionIntelligenceEngine:
    """Deterministic institutional decision-quality layer.

    M76.2 intentionally does not learn or self-modify.  It converts already-governed
    Stock Intelligence evidence into an explainable quality vector, an uncalibrated
    barrier-probability prior, decision readiness, and cross-sectional competition.
    """

    VERSION = "M76.2-IDI-1.0"

    _RS = {
        "A+": 96.0, "A": 90.0, "A-": 85.0,
        "B+": 78.0, "B": 72.0, "B-": 66.0,
        "C+": 58.0, "C": 52.0, "C-": 46.0,
        "D": 35.0, "F": 20.0,
    }

    def assess(self, profile: StockIntelligenceProfile) -> InstitutionalDecisionAssessment:
        scores = profile.scores
        plan = profile.trade_plan
        primary = profile.timeframe_states.get(profile.primary_timeframe)
        certification = dict(getattr(plan, "certification", {}) or {}) if plan else {}
        cert_pass = str(certification.get("status") or "").upper() == "PASS"

        directional = self._directional_quality(profile)
        trend = _clip((_num(getattr(primary, "trend_strength", 50), 50) * 0.55) + (_num(getattr(primary, "confidence", 50), 50) * 0.45))
        structure = self._structure_quality(profile)
        breakout = self._breakout_quality(profile)
        volume = _num(getattr(profile.institutional_volume, "institutional_participation_score", 50), 50)
        participation = _num(getattr(profile.participation, "score", 50), 50)
        relative_strength = self._RS.get(str(getattr(profile.context, "relative_strength_grade", "") or "").upper(), 50.0)
        market_alignment = _num(getattr(profile.context, "score", 50), 50)
        dealer = self._dealer_quality(profile)
        liquidity = self._liquidity_proxy(profile)
        risk = self._risk_quality(plan)
        management = _num(getattr(plan, "management_quality", 0), 0) if plan else 0.0
        certification_quality = _num(certification.get("quality_score"), 0.0) if certification else 0.0
        freshness = _num(getattr(scores, "freshness", 100), 100) if scores else 100.0

        barrier = self._barrier_probability(profile, directional, trend, structure, volume, market_alignment)
        target_quality = _clip(
            barrier.target_1_before_stop * 0.70
            + barrier.target_2_before_stop * 0.20
            + barrier.target_3_before_stop * 0.10
        )

        quality_vector = {
            "directional_quality": round(directional, 2),
            "trend_quality": round(trend, 2),
            "structure_quality": round(structure, 2),
            "breakout_quality": round(breakout, 2),
            "institutional_volume_quality": round(volume, 2),
            "participation_quality": round(participation, 2),
            "relative_strength_quality": round(relative_strength, 2),
            "market_alignment": round(market_alignment, 2),
            "dealer_quality": round(dealer, 2),
            "liquidity_quality": round(liquidity, 2),
            "risk_quality": round(risk, 2),
            "target_quality": round(target_quality, 2),
            "management_quality": round(management, 2),
            "certification_quality": round(certification_quality, 2),
        }
        weights = {
            "directional_quality": 0.09,
            "trend_quality": 0.08,
            "structure_quality": 0.11,
            "breakout_quality": 0.08,
            "institutional_volume_quality": 0.09,
            "participation_quality": 0.06,
            "relative_strength_quality": 0.07,
            "market_alignment": 0.07,
            "dealer_quality": 0.04,
            "liquidity_quality": 0.05,
            "risk_quality": 0.08,
            "target_quality": 0.08,
            "management_quality": 0.06,
            "certification_quality": 0.04,
        }
        overall = sum(quality_vector[key] * weight for key, weight in weights.items())
        if not cert_pass:
            overall = min(overall, 59.0)

        opportunity_freshness, aging_evidence = self._opportunity_freshness(profile, freshness)
        readiness = self._decision_readiness(profile, overall, opportunity_freshness, cert_pass)
        capital_priority = _clip(overall * 0.58 + readiness * 0.32 + risk * 0.10)
        grade = self._grade(overall, readiness, cert_pass)
        decision = self._decision(overall, readiness, cert_pass)
        lifecycle = self._lifecycle(profile, readiness)

        evidence = self._evidence_registry(quality_vector, barrier, aging_evidence)
        warnings: list[str] = []
        if not cert_pass:
            warnings.append("TRADE_PLAN_NOT_CERTIFIED")
        if readiness < 55:
            warnings.append("DECISION_READINESS_BELOW_PREFERRED_THRESHOLD")
        if opportunity_freshness < 60:
            warnings.append("OPPORTUNITY_AGING_OR_EXTENSION_RISK")
        if barrier.target_1_before_stop < 50:
            warnings.append("TARGET_1_BARRIER_PRIOR_BELOW_50")

        explainability = {
            "version": "M76.2.1-EXPLAINABILITY-1.0",
            "trade_quality": {
                "score": round(overall, 2),
                "components": [
                    {
                        "key": key,
                        "score": round(quality_vector[key], 2),
                        "weight": round(weights[key], 4),
                        "contribution": round(quality_vector[key] * weights[key], 2),
                    }
                    for key in weights
                ],
                "ranking_basis": "DETERMINISTIC_WEIGHTED_QUALITY_VECTOR",
            },
            "decision_readiness": {
                "score": round(readiness, 2),
                "certified": cert_pass,
                "components": {
                    "trade_quality": {"score": round(overall, 2), "weight": 0.42, "contribution": round(overall * 0.42, 2)},
                    "opportunity_freshness": {"score": round(opportunity_freshness, 2), "weight": 0.20, "contribution": round(opportunity_freshness * 0.20, 2)},
                    "management_quality": {"score": round(management, 2), "weight": 0.15, "contribution": round(management * 0.15, 2)},
                    "confidence": {"score": round(_num(profile.confidence, 0), 2), "weight": 0.13, "contribution": round(_num(profile.confidence, 0) * 0.13, 2)},
                    "institutional_volume": {"score": round(volume, 2), "weight": 0.10, "contribution": round(volume * 0.10, 2)},
                },
                "fail_closed_cap": 35.0 if not cert_pass else None,
            },
            "capital_priority": {
                "score": round(capital_priority, 2),
                "components": {
                    "trade_quality": {"score": round(overall, 2), "weight": 0.58, "contribution": round(overall * 0.58, 2)},
                    "decision_readiness": {"score": round(readiness, 2), "weight": 0.32, "contribution": round(readiness * 0.32, 2)},
                    "risk_quality": {"score": round(risk, 2), "weight": 0.10, "contribution": round(risk * 0.10, 2)},
                },
                "ranking_basis": "CAPITAL_PRIORITY_THEN_TRADE_QUALITY",
            },
            "opportunity_freshness": {
                "score": round(opportunity_freshness, 2),
                **aging_evidence,
            },
            "barrier_probability": {
                "target_1_before_stop": barrier.target_1_before_stop,
                "target_2_before_stop": barrier.target_2_before_stop,
                "target_3_before_stop": barrier.target_3_before_stop,
                "expected_mfe_pct": barrier.expected_mfe_pct,
                "expected_mae_pct": barrier.expected_mae_pct,
                "expected_holding_days": barrier.expected_holding_days,
                "model": barrier.model,
                "calibration_status": barrier.calibration_status,
            },
        }

        learning_snapshot = {
            "mode": "SHADOW_CAPTURE",
            "adaptive_influence": False,
            "feature_version": self.VERSION,
            "features": {
                **quality_vector,
                "barrier_t1": barrier.target_1_before_stop,
                "barrier_t2": barrier.target_2_before_stop,
                "barrier_t3": barrier.target_3_before_stop,
                "structural_reward_risk": _num(getattr(plan, "structural_reward_risk", 0), 0) if plan else 0.0,
                "alignment_score": _num(profile.alignment_score, 0),
                "relative_volume_1d": _num(getattr(profile.institutional_volume, "relative_volume_1d", 0), 0),
            },
            "outcome_fields_pending": ["MFE", "MAE", "TARGET_SEQUENCE", "STOP_HIT", "HOLDING_PERIOD", "REALIZED_RETURN"],
        }

        return InstitutionalDecisionAssessment(
            version=self.VERSION,
            overall_trade_quality=round(overall, 2),
            decision_readiness=round(readiness, 2),
            capital_priority=round(capital_priority, 2),
            opportunity_freshness=round(opportunity_freshness, 2),
            institutional_grade=grade,
            decision=decision,
            opportunity_lifecycle=lifecycle,
            quality_vector=quality_vector,
            barrier_probability=barrier,
            explainability=explainability,
            evidence_registry=evidence,
            warnings=warnings,
            competition={"status": "PENDING_POPULATION_RANKING"},
            learning_snapshot=learning_snapshot,
        ).finalize()

    def rank_population(self, profiles: list[StockIntelligenceProfile]) -> list[StockIntelligenceProfile]:
        assessed = [p for p in profiles if getattr(p, "decision_intelligence", None) is not None]
        ordered = sorted(
            assessed,
            key=lambda p: (
                _num(p.decision_intelligence.capital_priority),
                _num(p.decision_intelligence.overall_trade_quality),
                _num(p.decision_intelligence.decision_readiness),
                p.symbol,
            ),
            reverse=True,
        )
        total = max(1, len(ordered))
        for rank, profile in enumerate(ordered, start=1):
            assessment = profile.decision_intelligence
            assessment.competition = {
                "status": "READY",
                "market_rank": rank,
                "population_size": len(ordered),
                "market_percentile": round(100.0 * (total - rank + 1) / total, 2),
                "top_percent": round(100.0 * rank / total, 2),
                "rank_label": f"Rank #{rank} / {len(ordered)}",
                "ranking_basis": "CAPITAL_PRIORITY_THEN_TRADE_QUALITY",
                "version": self.VERSION,
            }
            assessment.finalize()
            profile.finalize()
        return ordered

    def _directional_quality(self, profile: StockIntelligenceProfile) -> float:
        if not profile.scores:
            return 50.0
        bearish = "BEAR" in str(profile.direction).upper()
        return _num(profile.scores.bearish if bearish else profile.scores.bullish, 50)

    def _structure_quality(self, profile: StockIntelligenceProfile) -> float:
        zones = [z for z in profile.structure_zones if str(z.status).upper() in {"OVERHEAD", "BELOW_PRICE", "AT_PRICE", "BROKEN"}]
        if not zones:
            return 50.0
        ranked = sorted(zones, key=lambda z: (_num(z.relevance_score), _num(z.confluence_score), _num(z.strength)), reverse=True)[:4]
        components = []
        for zone in ranked:
            components.append(
                _clip(
                    _num(zone.strength) * 0.30
                    + _num(zone.confluence_score) * 0.30
                    + _num(zone.relevance_score) * 0.20
                    + _num(zone.holding_probability, 0.5) * 100.0 * 0.20
                )
            )
        return sum(components) / len(components)

    def _breakout_quality(self, profile: StockIntelligenceProfile) -> float:
        if not profile.breakout:
            return 50.0
        state = str(profile.breakout.state or "NONE").upper()
        confirmation = _num(profile.breakout.confirmation, 0)
        follow = _num(profile.breakout.follow_through_probability, 50)
        failure = _num(profile.breakout.failure_probability, 50)
        base = confirmation * 0.50 + follow * 0.35 + (100.0 - failure) * 0.15
        if state in {"BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED", "BREAKOUT_RETEST", "BREAKDOWN_RETEST"}:
            base += 8.0
        elif "FAILED" in state:
            base -= 20.0
        return _clip(base)

    def _dealer_quality(self, profile: StockIntelligenceProfile) -> float:
        positioning = str(getattr(profile.context, "dealer_positioning", "NEUTRAL") or "NEUTRAL").upper()
        direction = str(profile.direction or "").upper()
        if positioning in {"NEUTRAL", "UNKNOWN", "UNAVAILABLE", ""}:
            return 50.0
        bullish = "BULL" in direction
        if (bullish and any(token in positioning for token in ("BULL", "SUPPORT", "POSITIVE"))) or ((not bullish) and "BEAR" in direction and any(token in positioning for token in ("BEAR", "PRESSURE", "NEGATIVE"))):
            return 80.0
        if any(token in positioning for token in ("MIXED", "BALANCED")):
            return 55.0
        return 35.0

    def _liquidity_proxy(self, profile: StockIntelligenceProfile) -> float:
        volume = profile.institutional_volume
        if not volume:
            return 50.0
        percentile = _num(getattr(volume, "volume_percentile_60d", 50), 50)
        rvol = _num(getattr(volume, "relative_volume_1d", 1), 1)
        return _clip(percentile * 0.65 + _clip(50 + (rvol - 1.0) * 30.0) * 0.35)

    def _risk_quality(self, plan: Any) -> float:
        if not plan:
            return 0.0
        rr = max(0.0, _num(getattr(plan, "structural_reward_risk", 0), 0))
        return _clip(35.0 + min(4.0, rr) * 16.0)

    def _barrier_probability(self, profile: StockIntelligenceProfile, directional: float, trend: float, structure: float, volume: float, market: float) -> BarrierProbabilityAssessment:
        plan = profile.trade_plan
        if not plan or not plan.entry or not plan.stop or not plan.targets.targets:
            return BarrierProbabilityAssessment(evidence={"warning": "insufficient governed geometry"})
        entry = _num(plan.entry.preferred_entry or ((plan.entry.zone_low or 0) + (plan.entry.zone_high or 0)) / 2.0, 0)
        stop = _num(plan.stop.recommended_stop, 0)
        targets = [_num(item.price, 0) for item in plan.targets.targets[:3]]
        if entry <= 0 or stop <= 0:
            return BarrierProbabilityAssessment(evidence={"warning": "invalid entry/stop geometry"})
        bullish = "BULL" in str(profile.direction).upper()
        risk_distance = (entry - stop) if bullish else (stop - entry)
        if risk_distance <= 0:
            return BarrierProbabilityAssessment(evidence={"warning": "invalid directional risk distance"})

        edge = ((_clip(directional) + _clip(trend) + _clip(structure) + _clip(volume) + _clip(market)) / 5.0 - 50.0) / 50.0
        probabilities: list[float] = []
        for target in targets:
            reward_distance = (target - entry) if bullish else (entry - target)
            if reward_distance <= 0:
                probabilities.append(0.0)
                continue
            driftless = risk_distance / (risk_distance + reward_distance)
            distance_penalty = min(0.65, reward_distance / max(entry, 1e-9))
            adjusted = _sigmoid(_logit(driftless) + edge * 1.25 - distance_penalty * 0.50)
            probabilities.append(_clip(adjusted * 100.0, 1.0, 99.0))
        while len(probabilities) < 3:
            probabilities.append(0.0)

        primary = profile.timeframe_states.get(profile.primary_timeframe)
        atr = _num(getattr(primary, "atr", 0), 0)
        atr_pct = atr / entry * 100.0 if entry > 0 else 0.0
        hold = max(1, int(_num(getattr(plan, "expected_hold_days", 10), 10)))
        composite = (directional + trend + structure + volume + market) / 500.0
        mfe = min(60.0, atr_pct * sqrt(min(hold, 30)) * (0.72 + composite * 0.55))
        mae = min(35.0, atr_pct * sqrt(min(hold, 30)) * (0.48 + (1.0 - composite) * 0.30))
        return BarrierProbabilityAssessment(
            target_1_before_stop=round(probabilities[0], 2),
            target_2_before_stop=round(probabilities[1], 2),
            target_3_before_stop=round(probabilities[2], 2),
            expected_mfe_pct=round(mfe, 2),
            expected_mae_pct=round(mae, 2),
            expected_holding_days=hold,
            evidence={
                "entry": round(entry, 4), "stop": round(stop, 4), "targets": [round(x, 4) for x in targets],
                "risk_distance": round(risk_distance, 4), "quality_edge": round(edge, 4),
                "atr": round(atr, 4), "atr_pct": round(atr_pct, 4),
                "note": "Deterministic prior only; outcome calibration is intentionally not active in M76.2.",
            },
        )

    def _opportunity_freshness(self, profile: StockIntelligenceProfile, base_freshness: float) -> tuple[float, dict[str, Any]]:
        plan = profile.trade_plan
        primary = profile.timeframe_states.get(profile.primary_timeframe)
        if not plan or not primary or not plan.entry:
            return _clip(base_freshness), {"status": "NO_GEOMETRY"}
        price = _num(primary.close, 0)
        atr = max(_num(primary.atr, 0), 1e-9)
        low = _num(plan.entry.zone_low, price)
        high = _num(plan.entry.zone_high, price)
        bullish = "BULL" in str(profile.direction).upper()
        extension = max(0.0, price - high) if bullish else max(0.0, low - price)
        extension_atr = extension / atr
        penalty = min(55.0, extension_atr * 22.0)
        freshness = _clip(base_freshness - penalty)
        return freshness, {"reference_price": price, "entry_zone": [low, high], "extension_atr": round(extension_atr, 3), "aging_penalty": round(penalty, 2)}

    def _decision_readiness(self, profile: StockIntelligenceProfile, quality: float, opportunity_freshness: float, certified: bool) -> float:
        if not certified:
            return min(35.0, quality * 0.45)
        plan = profile.trade_plan
        management = _num(getattr(plan, "management_quality", 0), 0) if plan else 0.0
        confidence = _num(profile.confidence, 0)
        volume = _num(getattr(profile.institutional_volume, "institutional_participation_score", 50), 50)
        return _clip(quality * 0.42 + opportunity_freshness * 0.20 + management * 0.15 + confidence * 0.13 + volume * 0.10)

    def _grade(self, quality: float, readiness: float, certified: bool) -> str:
        if not certified:
            return "NOT_CERTIFIED"
        score = min(quality, readiness)
        if score >= 90: return "A+"
        if score >= 85: return "A"
        if score >= 80: return "A-"
        if score >= 75: return "B+"
        if score >= 70: return "B"
        if score >= 65: return "B-"
        if score >= 60: return "C+"
        return "C"

    def _decision(self, quality: float, readiness: float, certified: bool) -> str:
        if not certified: return "BLOCK"
        if quality >= 82 and readiness >= 80: return "PRIORITIZE"
        if quality >= 72 and readiness >= 68: return "ELIGIBLE"
        if readiness >= 55: return "WATCH"
        return "WAIT"

    def _lifecycle(self, profile: StockIntelligenceProfile, readiness: float) -> str:
        state = str(getattr(profile.breakout, "state", "NONE") or "NONE").upper()
        structure = str(profile.structure or "").upper()
        if "FAILED" in state: return "INVALIDATION_RISK"
        if state in {"BREAKOUT_SETUP", "BREAKDOWN_SETUP"}: return "BREAKOUT_READY"
        if state in {"BREAKOUT_CONFIRMED", "BREAKDOWN_CONFIRMED"}: return "BREAKOUT"
        if state in {"BREAKOUT_RETEST", "BREAKDOWN_RETEST"}: return "RETEST"
        if structure == "EXPANSION": return "TREND_EXPANSION"
        if structure == "MATURE_TREND": return "MATURE"
        if structure == "EXHAUSTION": return "EXTENDED"
        if readiness >= 70: return "ACTIONABLE"
        return "DISCOVERED"

    def _evidence_registry(self, vector: dict[str, float], barrier: BarrierProbabilityAssessment, aging: dict[str, Any]) -> list[dict[str, Any]]:
        labels = {
            "directional_quality": "Directional thesis",
            "trend_quality": "Trend",
            "structure_quality": "Structure",
            "breakout_quality": "Breakout / breakdown",
            "institutional_volume_quality": "Institutional volume",
            "participation_quality": "Participation",
            "relative_strength_quality": "Relative strength",
            "market_alignment": "Market alignment",
            "dealer_quality": "Dealer context",
            "liquidity_quality": "Underlying liquidity proxy",
            "risk_quality": "Risk geometry",
            "target_quality": "Barrier / target quality",
            "management_quality": "Management",
            "certification_quality": "Trade-plan certification",
        }
        rows = [{"key": key, "label": labels.get(key, key), "score": round(value, 2), "status": "STRONG" if value >= 80 else "SUPPORTIVE" if value >= 65 else "MIXED" if value >= 50 else "WEAK"} for key, value in vector.items()]
        rows.append({"key": "barrier_probability", "label": "Target 1 before stop", "score": barrier.target_1_before_stop, "status": "UNCALIBRATED_PRIOR", "details": barrier.evidence})
        rows.append({"key": "opportunity_aging", "label": "Opportunity aging", "score": None, "status": "MEASURED", "details": aging})
        return rows
