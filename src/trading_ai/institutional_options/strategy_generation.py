from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from .domain import (
    InstitutionalOpportunity,
    OpportunityLineage,
    OpportunityState,
    OpportunityThesis,
    StrategyCandidate,
    StrategyComparison,
    StrategyDisposition,
    ThesisDirection,
)
from .models import InstitutionalOpportunityModel, OpportunityThesisModel, StrategyCandidateModel
from .repository import InstitutionalOpportunityRepository


@dataclass(frozen=True)
class StrategyEligibilityPolicy:
    minimum_eligibility_score: float = 50.0
    maximum_candidates_per_opportunity: int = 12
    policy_version: str = "M62-PH3-1.0"


@dataclass(frozen=True)
class StrategyGenerationResult:
    requested: int
    generated: int
    failed: int
    eligible_candidates: int
    rejected_candidates: int
    comparisons: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    directions: frozenset[ThesisDirection]
    preferred_regimes: frozenset[str]
    preferred_structures: frozenset[str]
    preferred_categories: frozenset[str]
    complexity: str
    base_score: float
    volatility_bias: str
    rationale: str


_STRATEGIES: tuple[StrategyDefinition, ...] = (
    StrategyDefinition("LONG_CALL", frozenset({ThesisDirection.BULLISH}), frozenset({"UPTREND", "BULLISH", "RISK_ON"}), frozenset({"TRENDING", "EXPANSION", "EARLY_TREND"}), frozenset({"BREAKOUT", "TREND_CONTINUATION", "ACCUMULATION"}), "LOW", 74, "LOW_TO_MODERATE_IV", "Direct bullish participation with convex upside"),
    StrategyDefinition("BULL_CALL_SPREAD", frozenset({ThesisDirection.BULLISH}), frozenset({"UPTREND", "BULLISH", "RISK_ON"}), frozenset({"TRENDING", "EXPANSION", "MATURE_TREND"}), frozenset({"BREAKOUT", "TREND_CONTINUATION", "ACCUMULATION"}), "LOW", 80, "MODERATE_TO_HIGH_IV", "Defined-risk bullish participation with reduced volatility cost"),
    StrategyDefinition("BULL_PUT_SPREAD", frozenset({ThesisDirection.BULLISH}), frozenset({"UPTREND", "BULLISH", "RANGE_BOUND", "POSITIVE_GAMMA"}), frozenset({"SIDEWAYS", "COMPRESSION", "TRENDING"}), frozenset({"MEAN_REVERSION_LONG", "ACCUMULATION", "TREND_CONTINUATION"}), "MEDIUM", 68, "HIGH_IV", "Defined-risk bullish premium sale above structural support"),
    StrategyDefinition("CALL_DIAGONAL", frozenset({ThesisDirection.BULLISH}), frozenset({"UPTREND", "BULLISH", "TRANSITION"}), frozenset({"TRENDING", "MATURE_TREND", "SIDEWAYS"}), frozenset({"TREND_CONTINUATION", "ACCUMULATION"}), "HIGH", 66, "TERM_STRUCTURE", "Bullish time-spread expression with controlled front-leg decay"),
    StrategyDefinition("CALL_CALENDAR", frozenset({ThesisDirection.BULLISH}), frozenset({"TRANSITION", "RANGE_BOUND", "LOW_VOLATILITY"}), frozenset({"COMPRESSION", "SIDEWAYS"}), frozenset({"BREAKOUT", "ACCUMULATION", "REVERSAL"}), "HIGH", 62, "LOW_FRONT_IV", "Bullish or neutral volatility-term-structure expression"),
    StrategyDefinition("LONG_PUT", frozenset({ThesisDirection.BEARISH}), frozenset({"DOWNTREND", "BEARISH", "RISK_OFF"}), frozenset({"TRENDING", "EXPANSION", "EARLY_TREND"}), frozenset({"BREAKDOWN", "TREND_CONTINUATION", "DISTRIBUTION"}), "LOW", 74, "LOW_TO_MODERATE_IV", "Direct bearish participation with convex downside"),
    StrategyDefinition("BEAR_PUT_SPREAD", frozenset({ThesisDirection.BEARISH}), frozenset({"DOWNTREND", "BEARISH", "RISK_OFF"}), frozenset({"TRENDING", "EXPANSION", "MATURE_TREND"}), frozenset({"BREAKDOWN", "TREND_CONTINUATION", "DISTRIBUTION"}), "LOW", 80, "MODERATE_TO_HIGH_IV", "Defined-risk bearish participation with reduced volatility cost"),
    StrategyDefinition("BEAR_CALL_SPREAD", frozenset({ThesisDirection.BEARISH}), frozenset({"DOWNTREND", "BEARISH", "RANGE_BOUND", "POSITIVE_GAMMA"}), frozenset({"SIDEWAYS", "COMPRESSION", "TRENDING"}), frozenset({"MEAN_REVERSION_SHORT", "DISTRIBUTION", "TREND_CONTINUATION"}), "MEDIUM", 68, "HIGH_IV", "Defined-risk bearish premium sale below structural resistance"),
    StrategyDefinition("PUT_DIAGONAL", frozenset({ThesisDirection.BEARISH}), frozenset({"DOWNTREND", "BEARISH", "TRANSITION"}), frozenset({"TRENDING", "MATURE_TREND", "SIDEWAYS"}), frozenset({"TREND_CONTINUATION", "DISTRIBUTION"}), "HIGH", 66, "TERM_STRUCTURE", "Bearish time-spread expression with controlled front-leg decay"),
    StrategyDefinition("PUT_CALENDAR", frozenset({ThesisDirection.BEARISH}), frozenset({"TRANSITION", "RANGE_BOUND", "LOW_VOLATILITY"}), frozenset({"COMPRESSION", "SIDEWAYS"}), frozenset({"BREAKDOWN", "DISTRIBUTION", "REVERSAL"}), "HIGH", 62, "LOW_FRONT_IV", "Bearish or neutral volatility-term-structure expression"),
    StrategyDefinition("IRON_CONDOR", frozenset({ThesisDirection.BULLISH, ThesisDirection.BEARISH}), frozenset({"RANGE_BOUND", "POSITIVE_GAMMA", "LOW_CORRELATION"}), frozenset({"SIDEWAYS", "COMPRESSION"}), frozenset({"MEAN_REVERSION_LONG", "MEAN_REVERSION_SHORT", "RANGE"}), "HIGH", 60, "HIGH_IV", "Defined-risk range expression when structural containment is strong"),
    StrategyDefinition("IRON_BUTTERFLY", frozenset({ThesisDirection.BULLISH, ThesisDirection.BEARISH}), frozenset({"RANGE_BOUND", "POSITIVE_GAMMA"}), frozenset({"SIDEWAYS", "COMPRESSION"}), frozenset({"MEAN_REVERSION_LONG", "MEAN_REVERSION_SHORT", "RANGE"}), "HIGH", 56, "HIGH_IV", "Concentrated defined-risk range expression around a strong structural center"),
)


def _norm(value: str | None) -> str:
    return str(value or "").strip().upper()


def _contains_any(value: str, options: Iterable[str]) -> bool:
    normalized = _norm(value)
    return any(_norm(option) in normalized or normalized in _norm(option) for option in options if option)


class RegimeAwareStrategyEligibilityService:
    def __init__(self, policy: StrategyEligibilityPolicy | None = None) -> None:
        self.policy = policy or StrategyEligibilityPolicy()

    def generate(self, opportunity: InstitutionalOpportunity, thesis: OpportunityThesis) -> list[StrategyCandidate]:
        candidates: list[StrategyCandidate] = []
        for definition in _STRATEGIES[: self.policy.maximum_candidates_per_opportunity]:
            accepted: list[str] = []
            rejected: list[str] = []
            score = float(definition.base_score)

            if thesis.direction not in definition.directions:
                rejected.append("DIRECTION_INCOMPATIBLE")
                score -= 60
            else:
                accepted.append(f"Direction compatible: {thesis.direction.value}")
                score += 8

            market_regime = _norm(thesis.market_regime)
            structure = _norm(thesis.structure_state)
            category = _norm(thesis.setup_category)
            participation = _norm(thesis.participation_state)
            dealer = _norm(thesis.dealer_context)
            forecast = _norm(thesis.forecast_context)

            if market_regime and _contains_any(market_regime, definition.preferred_regimes):
                score += 8
                accepted.append(f"Market regime compatible: {market_regime}")
            elif market_regime:
                score -= 6
                rejected.append(f"MARKET_REGIME_MISMATCH:{market_regime}")
            else:
                rejected.append("MARKET_REGIME_UNAVAILABLE")

            if structure and _contains_any(structure, definition.preferred_structures):
                score += 8
                accepted.append(f"Structure compatible: {structure}")
            elif structure:
                score -= 5
                rejected.append(f"STRUCTURE_MISMATCH:{structure}")

            if category and _contains_any(category, definition.preferred_categories):
                score += 8
                accepted.append(f"Setup compatible: {category}")
            elif category:
                score -= 4

            directional_word = "BULL" if thesis.direction == ThesisDirection.BULLISH else "BEAR"
            if forecast and directional_word in forecast:
                score += 6
                accepted.append("Forecast supports thesis direction")
            elif forecast and any(word in forecast for word in ("BULL", "BEAR")):
                score -= 10
                rejected.append("FORECAST_DIRECTION_CONFLICT")

            if participation in {"ACCUMULATION", "RE_ACCUMULATION"} and thesis.direction == ThesisDirection.BULLISH:
                score += 5
                accepted.append("Institutional accumulation supports bullish thesis")
            elif participation in {"DISTRIBUTION", "RE_DISTRIBUTION"} and thesis.direction == ThesisDirection.BEARISH:
                score += 5
                accepted.append("Institutional distribution supports bearish thesis")

            if "POSITIVE_GAMMA" in dealer and definition.name in {"BULL_PUT_SPREAD", "BEAR_CALL_SPREAD", "IRON_CONDOR", "IRON_BUTTERFLY"}:
                score += 6
                accepted.append("Positive gamma supports bounded premium strategy")
            if "NEGATIVE_GAMMA" in dealer and definition.name in {"LONG_CALL", "LONG_PUT", "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD"}:
                score += 5
                accepted.append("Negative gamma supports directional expansion")

            score += min(8.0, max(-8.0, (opportunity.overall_score - 70.0) * 0.2))
            score += min(6.0, max(-6.0, (opportunity.confidence - 70.0) * 0.15))
            score = round(max(0.0, min(100.0, score)), 4)

            hard_rejection = "DIRECTION_INCOMPATIBLE" in rejected or "FORECAST_DIRECTION_CONFLICT" in rejected
            eligible = (not hard_rejection) and score >= self.policy.minimum_eligibility_score
            disposition = StrategyDisposition.ELIGIBLE if eligible else StrategyDisposition.REJECTED
            if not eligible and not hard_rejection and score < self.policy.minimum_eligibility_score:
                rejected.append("ELIGIBILITY_SCORE_BELOW_MINIMUM")

            candidates.append(StrategyCandidate(
                strategy_candidate_id=f"m62-strategy-{uuid4().hex}",
                opportunity_id=opportunity.opportunity_id,
                strategy=definition.name,
                disposition=disposition,
                eligibility_score=score,
                strategy_score=score if eligible else None,
                complexity=definition.complexity,
                accepted_reasons=tuple(accepted + [definition.rationale]),
                rejection_reasons=tuple(rejected),
                metadata={
                    "volatility_bias": definition.volatility_bias,
                    "policy_version": self.policy.policy_version,
                    "market_regime": thesis.market_regime,
                    "structure_state": thesis.structure_state,
                    "setup_category": thesis.setup_category,
                },
            ))
        return candidates


class InstitutionalStrategyGenerationService:
    def __init__(self, session: Session, policy: StrategyEligibilityPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or StrategyEligibilityPolicy()
        self.eligibility = RegimeAwareStrategyEligibilityService(self.policy)
        self.repository = InstitutionalOpportunityRepository(session)

    def generate(self, *, opportunity_ids: Iterable[str] | None = None, limit: int | None = None) -> StrategyGenerationResult:
        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state == OpportunityState.VALIDATED.value
        )
        if opportunity_ids:
            query = query.filter(InstitutionalOpportunityModel.opportunity_id.in_(tuple(opportunity_ids)))
        rows = query.order_by(InstitutionalOpportunityModel.overall_score.desc(), InstitutionalOpportunityModel.symbol)
        if limit is not None:
            rows = rows.limit(limit)
        opportunities = rows.all()

        generated = failed = eligible_count = rejected_count = comparisons = 0
        errors: list[str] = []
        for row in opportunities:
            opportunity_id = row.opportunity_id
            try:
                with self.session.begin_nested():
                    thesis_row = self.session.query(OpportunityThesisModel).filter(
                        OpportunityThesisModel.opportunity_id == opportunity_id
                    ).one()
                    opportunity_payload = dict(row.payload_json or {})
                    thesis_payload = dict(thesis_row.payload_json or {})
                    opportunity = InstitutionalOpportunity(
                        opportunity_id=opportunity_id,
                        symbol=row.symbol,
                        asset_class=row.asset_class,
                        state=OpportunityState(row.state),
                        direction=ThesisDirection(row.direction),
                        category=row.category,
                        overall_score=row.overall_score,
                        confidence=row.confidence,
                        conviction=row.conviction,
                        lineage=OpportunityLineage(**opportunity_payload["lineage"]),
                        thesis_id=row.thesis_id,
                        version=row.version,
                        created_at=row.created_at,
                        updated_at=row.updated_at,
                        metadata=opportunity_payload.get("metadata") or {},
                    )
                    thesis = OpportunityThesis(
                        thesis_id=thesis_row.thesis_id,
                        opportunity_id=opportunity_id,
                        direction=ThesisDirection(thesis_row.direction),
                        setup_category=thesis_row.setup_category,
                        primary_timeframe=thesis_row.primary_timeframe,
                        market_regime=thesis_payload.get("market_regime"),
                        sector_context=thesis_payload.get("sector_context"),
                        trend_state=thesis_payload.get("trend_state") or "UNKNOWN",
                        structure_state=thesis_payload.get("structure_state") or "UNKNOWN",
                        participation_state=thesis_payload.get("participation_state"),
                        dealer_context=thesis_payload.get("dealer_context"),
                        forecast_context=thesis_payload.get("forecast_context"),
                        entry_zone_low=thesis_row.entry_zone_low,
                        entry_zone_high=thesis_row.entry_zone_high,
                        invalidation_level=thesis_row.invalidation_level,
                        targets=tuple(float(item) for item in thesis_payload.get("targets") or ()),
                        expected_holding_days_min=thesis_payload.get("expected_holding_days_min"),
                        expected_holding_days_max=thesis_payload.get("expected_holding_days_max"),
                        evidence=tuple(thesis_payload.get("evidence") or ()),
                        risks=tuple(thesis_payload.get("risks") or ()),
                        created_at=thesis_row.created_at,
                    )
                    candidates = self.eligibility.generate(opportunity, thesis)
                    eligible = sorted(
                        (item for item in candidates if item.disposition == StrategyDisposition.ELIGIBLE),
                        key=lambda item: (-item.eligibility_score, item.strategy),
                    )
                    rejected = [item for item in candidates if item.disposition == StrategyDisposition.REJECTED]

                    if not eligible:
                        self.repository.save_strategy_evaluations(rejected)
                        self.session.flush()
                        rejected_count += len(rejected)
                        failed += 1
                        errors.append(f"{opportunity_id}: ValueError: No eligible option strategies generated")
                        continue

                    ranked_candidates: list[StrategyCandidate] = []
                    for rank, candidate in enumerate(eligible, 1):
                        ranked_candidates.append(
                            replace(candidate, rank=rank, strategy_score=candidate.eligibility_score)
                        )
                    all_candidates = ranked_candidates + rejected
                    self.repository.save_strategy_candidates(all_candidates)
                    self.session.flush()

                    # Resolve canonical IDs after natural-key upsert so comparison
                    # lineage always references the stable persisted candidates.
                    persisted_ranked = self.session.query(StrategyCandidateModel).filter(
                        StrategyCandidateModel.opportunity_id == opportunity_id,
                        StrategyCandidateModel.disposition.in_((
                            StrategyDisposition.ELIGIBLE.value,
                            StrategyDisposition.SELECTED.value,
                        )),
                    ).order_by(
                        StrategyCandidateModel.rank.asc().nullslast(),
                        StrategyCandidateModel.eligibility_score.desc(),
                    ).all()
                    ranked_ids = tuple(item.strategy_candidate_id for item in persisted_ranked)
                    comparison = StrategyComparison(
                        comparison_id=f"m62-comparison-{uuid4().hex}",
                        opportunity_id=opportunity_id,
                        ranked_strategy_candidate_ids=ranked_ids,
                        selected_strategy_candidate_id=None,
                        comparison_policy_version=self.policy.policy_version,
                        rationale=(
                            "Strategies ranked by directional, regime, structure, setup, dealer, forecast, and opportunity-quality compatibility",
                            "Contract-level probability, liquidity, and capital efficiency are deferred to later optimization phases",
                        ),
                    )
                    self.repository.save_strategy_comparison(comparison)
                    self.repository.transition(
                        opportunity_id,
                        OpportunityState.STRATEGIES_GENERATED,
                        actor="m62_strategy_generation",
                        reason=f"Generated {len(eligible)} eligible strategies and {len(rejected)} explainable rejections",
                    )
                    generated += 1
                    eligible_count += len(eligible)
                    rejected_count += len(rejected)
                    comparisons += 1
            except Exception as exc:  # savepoint isolates each opportunity
                failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")
        return StrategyGenerationResult(
            requested=len(opportunities),
            generated=generated,
            failed=failed,
            eligible_candidates=eligible_count,
            rejected_candidates=rejected_count,
            comparisons=comparisons,
            errors=tuple(errors),
        )
