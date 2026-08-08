from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp, log
from typing import Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from .domain import (
    ContractRecommendation,
    deserialize_contract_recommendation,
    InstitutionalOpportunity,
    OpportunityLineage,
    OpportunityState,
    OpportunityThesis,
    ProbabilityDecomposition,
    StrategyCandidate,
    StrategyComparison,
    StrategyDisposition,
    ThesisDirection,
    ContractLegRecommendation,
    ContractSide,
)
from .models import (
    ContractRecommendationModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    StrategyCandidateModel,
)
from .repository import InstitutionalOpportunityRepository


@dataclass(frozen=True)
class StrategyValuationPolicy:
    minimum_probability: float = 0.52
    minimum_liquidity_score: float = 45.0
    minimum_expected_return_on_risk: float = -0.05
    maximum_tail_risk: float = 85.0
    probability_adjustment_cap: float = 0.15
    policy_version: str = "M62-PH5-1.0"


@dataclass(frozen=True)
class StrategyValuationResult:
    requested: int
    valued: int
    selected: int
    rejected: int
    failed: int
    errors: tuple[str, ...] = ()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mid(bid: float | None, ask: float | None, last: float | None) -> float:
    if bid is not None and ask is not None and bid >= 0 and ask >= bid:
        return (bid + ask) / 2.0
    return float(last or 0.0)


def _is_rankable_disposition(disposition: StrategyDisposition) -> bool:
    """Return whether a valuation can participate in winner selection.

    SELECTED is intentionally rankable so idempotent valuation rebuilds can
    refresh an already-selected candidate without first demoting it back to
    ELIGIBLE.
    """
    return disposition in {StrategyDisposition.ELIGIBLE, StrategyDisposition.SELECTED}


class ContractStrategyValuationEngine:
    def __init__(self, policy: StrategyValuationPolicy | None = None) -> None:
        self.policy = policy or StrategyValuationPolicy()

    def value(
        self,
        opportunity: InstitutionalOpportunity,
        thesis: OpportunityThesis,
        strategy: StrategyCandidate,
        contract: ContractRecommendation,
    ) -> StrategyCandidate:
        if not contract.executable or not contract.legs:
            return replace(
                strategy,
                disposition=StrategyDisposition.REJECTED,
                rejection_reasons=tuple(strategy.rejection_reasons) + ("CONTRACT_NOT_EXECUTABLE",),
                selected=False,
            )

        liquidity = float(contract.liquidity_score or 0.0)
        mids = [_mid(leg.bid, leg.ask, leg.last) * max(1, leg.quantity_ratio) for leg in contract.legs]
        buys = sum(value for value, leg in zip(mids, contract.legs) if leg.side.value == "BUY")
        sells = sum(value for value, leg in zip(mids, contract.legs) if leg.side.value == "SELL")
        debit = max(0.0, buys - sells)
        credit = max(0.0, sells - buys)
        multiplier = 100.0

        capital_required = max(1.0, (debit if debit > 0 else max(credit * 3.0, 1.0)) * multiplier)
        max_loss = capital_required
        target_distance = abs(thesis.targets[0] - ((thesis.entry_zone_low + thesis.entry_zone_high) / 2.0))
        stop_distance = abs(((thesis.entry_zone_low + thesis.entry_zone_high) / 2.0) - thesis.invalidation_level)
        structural_rr = target_distance / max(stop_distance, 1e-9)

        delta_signal = sum(abs(float(leg.delta or 0.0)) for leg in contract.legs) / max(1, len(contract.legs))
        raw_probability = _clamp(0.45 + 0.25 * delta_signal, 0.35, 0.78)
        underlying_probability = _clamp(0.45 + opportunity.confidence / 250.0, 0.45, 0.82)
        regime_adjustment = 0.03 if thesis.market_regime and thesis.direction.value in thesis.market_regime.upper() else 0.0
        structure_adjustment = _clamp((structural_rr - 1.0) * 0.025, -0.04, 0.06)
        dealer_adjustment = 0.0
        dealer = (thesis.dealer_context or "").upper()
        if thesis.direction.value in dealer:
            dealer_adjustment = 0.03
        elif dealer and any(word in dealer for word in ("BULL", "BEAR")):
            dealer_adjustment = -0.04
        liquidity_adjustment = _clamp((liquidity - 50.0) / 1000.0, -0.05, 0.05)
        total_adjustment = _clamp(
            (underlying_probability - 0.60) * 0.35
            + regime_adjustment
            + structure_adjustment
            + dealer_adjustment
            + liquidity_adjustment,
            -self.policy.probability_adjustment_cap,
            self.policy.probability_adjustment_cap,
        )
        final_probability = _clamp(raw_probability + total_adjustment, 0.01, 0.99)

        reward_multiple = _clamp(structural_rr, 0.25, 6.0)
        expected_value = final_probability * (max_loss * reward_multiple) - (1.0 - final_probability) * max_loss
        expected_return_on_risk = expected_value / max_loss
        tail_risk = _clamp(100.0 - min(100.0, liquidity) * 0.35 + max(0.0, 1.0 - structural_rr) * 25.0, 0.0, 100.0)
        capital_efficiency = _clamp((max(0.0, expected_value) / capital_required) * 100.0 + liquidity * 0.35, 0.0, 100.0)
        complexity_penalty = {"LOW": 0.0, "MEDIUM": 5.0, "HIGH": 10.0}.get(strategy.complexity.upper(), 7.0)
        composite = _clamp(
            final_probability * 45.0
            + _clamp(expected_return_on_risk, -1.0, 2.0) * 18.0
            + liquidity * 0.18
            + capital_efficiency * 0.12
            - tail_risk * 0.08
            - complexity_penalty,
            0.0,
            100.0,
        )

        rejections = list(strategy.rejection_reasons)
        if final_probability < self.policy.minimum_probability:
            rejections.append("PROBABILITY_BELOW_MINIMUM")
        if liquidity < self.policy.minimum_liquidity_score:
            rejections.append("LIQUIDITY_BELOW_MINIMUM")
        if expected_return_on_risk < self.policy.minimum_expected_return_on_risk:
            rejections.append("EXPECTED_RETURN_ON_RISK_BELOW_MINIMUM")
        if tail_risk > self.policy.maximum_tail_risk:
            rejections.append("TAIL_RISK_ABOVE_MAXIMUM")
        eligible = not rejections

        probability = ProbabilityDecomposition(
            underlying_probability=round(underlying_probability, 6),
            option_payoff_probability=round(raw_probability, 6),
            regime_adjustment=round(regime_adjustment, 6),
            structure_adjustment=round(structure_adjustment, 6),
            dealer_adjustment=round(dealer_adjustment, 6),
            liquidity_adjustment=round(liquidity_adjustment, 6),
            calibrated_probability=round(final_probability, 6),
            model_family="M62_RULE_BASED_CONTRACT_VALUATION",
            model_version=self.policy.policy_version,
        )
        evidence = tuple(strategy.accepted_reasons) + (
            f"Contract liquidity score {liquidity:.2f}",
            f"Structural reward/risk {structural_rr:.2f}",
            f"Calibrated probability {final_probability:.2%}",
            f"Expected return on risk {expected_return_on_risk:.2%}",
        )
        return replace(
            strategy,
            disposition=StrategyDisposition.ELIGIBLE if eligible else StrategyDisposition.REJECTED,
            strategy_score=round(composite, 4),
            capital_required=round(capital_required, 2),
            maximum_loss=round(max_loss, 2),
            expected_value=round(expected_value, 2),
            expected_return_on_risk=round(expected_return_on_risk, 6),
            structural_reward_risk=round(structural_rr, 6),
            probability=probability,
            accepted_reasons=evidence,
            rejection_reasons=tuple(rejections),
            selected=False,
            metadata=dict(strategy.metadata) | {
                "tail_risk_score": round(tail_risk, 4),
                "capital_efficiency_score": round(capital_efficiency, 4),
                "liquidity_score": round(liquidity, 4),
                "valuation_policy_version": self.policy.policy_version,
            },
        )


class InstitutionalStrategyValuationService:
    def __init__(self, session: Session, policy: StrategyValuationPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or StrategyValuationPolicy()
        self.engine = ContractStrategyValuationEngine(self.policy)
        self.repository = InstitutionalOpportunityRepository(session)

    def value(self, *, opportunity_ids: Iterable[str] | None = None, limit: int | None = None) -> StrategyValuationResult:
        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state == OpportunityState.CONTRACTS_OPTIMIZED.value
        )
        if opportunity_ids:
            query = query.filter(InstitutionalOpportunityModel.opportunity_id.in_(tuple(opportunity_ids)))
        rows = query.order_by(InstitutionalOpportunityModel.overall_score.desc(), InstitutionalOpportunityModel.symbol)
        if limit is not None:
            rows = rows.limit(limit)
        opportunities = rows.all()

        valued = selected = rejected = failed = 0
        errors: list[str] = []
        for row in opportunities:
            opportunity_id = str(row.opportunity_id)
            try:
                with self.session.begin_nested():
                    opportunity_payload = dict(row.payload_json or {})
                    opportunity = InstitutionalOpportunity(
                        **(opportunity_payload | {
                            "state": OpportunityState(opportunity_payload["state"]),
                            "direction": ThesisDirection(opportunity_payload["direction"]),
                            "lineage": OpportunityLineage(**opportunity_payload["lineage"]),
                        })
                    )
                    thesis_row = self.session.query(OpportunityThesisModel).filter_by(opportunity_id=row.opportunity_id).one()
                    thesis_payload = dict(thesis_row.payload_json or {})
                    thesis = OpportunityThesis(**(thesis_payload | {"direction": ThesisDirection(thesis_payload["direction"]), "targets": tuple(thesis_payload.get("targets") or ()) , "evidence": tuple(thesis_payload.get("evidence") or ()), "risks": tuple(thesis_payload.get("risks") or ())}))
                    strategy_rows = self.session.query(StrategyCandidateModel).filter_by(opportunity_id=row.opportunity_id).all()
                    contract_rows = (
                        self.session.query(ContractRecommendationModel)
                        .filter_by(opportunity_id=row.opportunity_id)
                        .order_by(
                            ContractRecommendationModel.executable.desc(),
                            ContractRecommendationModel.liquidity_score.desc().nullslast(),
                            ContractRecommendationModel.created_at.desc(),
                        )
                        .all()
                    )
                    # One authoritative contract recommendation is consumed per
                    # strategy candidate. Prefer executable, liquid, and newest
                    # rows deterministically; retain the first row selected by
                    # that ordering rather than allowing an arbitrary later row
                    # to overwrite it.
                    contracts: dict[str, ContractRecommendation] = {}
                    for contract_row in contract_rows:
                        strategy_candidate_id = str(contract_row.strategy_candidate_id)
                        if strategy_candidate_id in contracts:
                            continue
                        payload = dict(contract_row.payload_json or {})
                        contracts[strategy_candidate_id] = deserialize_contract_recommendation(payload)
                    valuations: list[StrategyCandidate] = []
                    for strategy_row in strategy_rows:
                        strategy_payload = dict(strategy_row.payload_json or {})
                        probability_payload = strategy_payload.get("probability")
                        strategy = StrategyCandidate(**(strategy_payload | {
                            "disposition": StrategyDisposition(strategy_payload["disposition"]),
                            "probability": None if not probability_payload else ProbabilityDecomposition(**probability_payload),
                            "accepted_reasons": tuple(strategy_payload.get("accepted_reasons") or ()),
                            "rejection_reasons": tuple(strategy_payload.get("rejection_reasons") or ()),
                        }))
                        contract = contracts.get(strategy.strategy_candidate_id)
                        if contract is None:
                            valuations.append(replace(
                                strategy,
                                disposition=StrategyDisposition.REJECTED,
                                selected=False,
                                rejection_reasons=tuple(strategy.rejection_reasons)
                                + ("CONTRACT_RECOMMENDATION_MISSING",),
                            ))
                            continue
                        valuations.append(self.engine.value(opportunity, thesis, strategy, contract))
                    ranked = sorted(
                        [
                            item
                            for item in valuations
                            if _is_rankable_disposition(item.disposition)
                        ],
                        key=lambda item: (-(item.strategy_score or 0.0), item.strategy),
                    )
                    selected_id = ranked[0].strategy_candidate_id if ranked else None
                    persisted: list[StrategyCandidate] = []
                    for item in valuations:
                        rank = next((index + 1 for index, candidate in enumerate(ranked) if candidate.strategy_candidate_id == item.strategy_candidate_id), None)
                        persisted.append(replace(item, rank=rank, selected=item.strategy_candidate_id == selected_id, disposition=StrategyDisposition.SELECTED if item.strategy_candidate_id == selected_id else item.disposition))
                    # An all-rejected valuation set is a valid governed
                    # outcome, not an infrastructure failure. Persist the full
                    # evaluation set without requiring an eligible candidate.
                    # Only the selected path uses the actionable-set validator.
                    if selected_id:
                        self.repository.save_strategy_candidates(persisted)
                    else:
                        self.repository.save_strategy_evaluations(persisted)
                    for item in persisted:
                        self.repository.save_strategy_valuation(f"m62-valuation-{uuid4().hex}", item)
                    comparison = StrategyComparison(
                        comparison_id=f"m62-comparison-{uuid4().hex}",
                        opportunity_id=row.opportunity_id,
                        ranked_strategy_candidate_ids=tuple(item.strategy_candidate_id for item in ranked),
                        selected_strategy_candidate_id=selected_id,
                        comparison_policy_version=self.policy.policy_version,
                        rationale=tuple(
                            [f"Selected {ranked[0].strategy} with score {ranked[0].strategy_score:.2f}"] if ranked else ["No strategy passed valuation governance"]
                        ),
                    )
                    self.repository.save_strategy_comparison(comparison)
                    valued += len(valuations)
                    rejected += len([item for item in valuations if item.disposition == StrategyDisposition.REJECTED])
                    if selected_id:
                        selected += 1
                        self.repository.transition(
                            row.opportunity_id,
                            OpportunityState.READY_FOR_EXECUTION,
                            "m62-phase5",
                            "Final valued strategy selected",
                        )
                    else:
                        self.repository.transition(
                            row.opportunity_id,
                            OpportunityState.REJECTED,
                            "m62-phase5",
                            "No contract recommendation passed strategy valuation governance",
                        )
            except Exception as exc:  # isolate opportunity failures
                failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")
        return StrategyValuationResult(len(opportunities), valued, selected, rejected, failed, tuple(errors))
