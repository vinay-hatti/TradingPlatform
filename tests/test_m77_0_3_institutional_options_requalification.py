from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.decision import InstitutionalDecisionService
from trading_ai.institutional_options.domain import (
    StrategyCandidate,
    StrategyDisposition,
)
from trading_ai.institutional_options.management import (
    DynamicManagementResult,
    InstitutionalDynamicManagementService,
)
from trading_ai.institutional_options.models import (
    ContractRecommendationModel,
    InstitutionalOpportunityModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
)
from trading_ai.institutional_options.repository import (
    InstitutionalOpportunityRepository,
)
from trading_ai.institutional_options.valuation import StrategyValuationResult


def _engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _opportunity(
    opportunity_id: str = "opp-requalify",
    *,
    state: str = "CONTRACTS_OPTIMIZED",
) -> InstitutionalOpportunityModel:
    return InstitutionalOpportunityModel(
        opportunity_id=opportunity_id,
        symbol="AAPL",
        asset_class="EQUITY",
        state=state,
        direction="BULLISH",
        category="TREND_CONTINUATION",
        overall_score=80.0,
        confidence=80.0,
        conviction="HIGH",
        thesis_id=f"thesis-{opportunity_id}",
        stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id="stock-run-current",
        stock_candidate_id=f"candidate-{opportunity_id}",
        stock_state_hash="state-hash",
        option_snapshot_id="options-current",
        version=2,
        created_at="2026-08-15T00:00:00+00:00",
        updated_at="2026-08-15T00:00:00+00:00",
        payload_json={},
    )


def _candidate(
    identifier: str,
    strategy: str,
    *,
    selected: bool,
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_candidate_id=identifier,
        opportunity_id="opp-selection",
        strategy=strategy,
        disposition=(
            StrategyDisposition.SELECTED
            if selected
            else StrategyDisposition.ELIGIBLE
        ),
        eligibility_score=80.0,
        strategy_score=80.0,
        selected=selected,
    )


def test_strategy_rebuild_replaces_prior_selection_exactly():
    with Session(_engine()) as session:
        repository = InstitutionalOpportunityRepository(session)
        repository.save_strategy_candidates(
            [
                _candidate("strategy-a", "LONG_CALL", selected=True),
                _candidate("strategy-b", "BULL_CALL_SPREAD", selected=False),
            ]
        )
        session.flush()
        repository.save_strategy_candidates(
            [
                _candidate("new-b", "BULL_CALL_SPREAD", selected=True),
            ]
        )
        session.commit()

        rows = session.query(StrategyCandidateModel).order_by(
            StrategyCandidateModel.strategy
        ).all()
        assert len(rows) == 2
        assert [row.strategy_candidate_id for row in rows] == [
            "strategy-b",
            "strategy-a",
        ]
        assert [row.selected for row in rows] == [True, False]
        assert [row.payload_json["selected"] for row in rows] == [True, False]


def test_management_uses_comparison_winner_and_current_contract_snapshot():
    with Session(_engine()) as session:
        opportunity = _opportunity()
        session.add(opportunity)
        session.add_all(
            [
                StrategyCandidateModel(
                    strategy_candidate_id="strategy-old",
                    opportunity_id=opportunity.opportunity_id,
                    strategy="LONG_CALL",
                    disposition="SELECTED",
                    eligibility_score=75.0,
                    strategy_score=75.0,
                    complexity="LOW",
                    rank=2,
                    selected=True,
                    payload_json={},
                ),
                StrategyCandidateModel(
                    strategy_candidate_id="strategy-current",
                    opportunity_id=opportunity.opportunity_id,
                    strategy="BULL_CALL_SPREAD",
                    disposition="SELECTED",
                    eligibility_score=85.0,
                    strategy_score=85.0,
                    complexity="MEDIUM",
                    rank=1,
                    selected=True,
                    payload_json={},
                ),
                StrategyComparisonModel(
                    comparison_id="comparison-current",
                    opportunity_id=opportunity.opportunity_id,
                    selected_strategy_candidate_id="strategy-current",
                    policy_version="M62-PH5-1.0",
                    created_at="2026-08-15T00:00:00+00:00",
                    payload_json={},
                ),
            ]
        )
        for contract_id, snapshot_id, strategy_id in (
            ("contract-old", "options-old", "strategy-current"),
            ("contract-current", "options-current", "strategy-current"),
            ("contract-other", "options-current", "strategy-old"),
        ):
            session.add(
                ContractRecommendationModel(
                    contract_recommendation_id=contract_id,
                    opportunity_id=opportunity.opportunity_id,
                    strategy_candidate_id=strategy_id,
                    option_snapshot_id=snapshot_id,
                    executable=True,
                    liquidity_score=90.0,
                    created_at="2026-08-15T00:00:00+00:00",
                    payload_json={},
                )
            )
        session.flush()

        service = InstitutionalDynamicManagementService(session)
        strategy = service._authoritative_strategy_row(opportunity)
        contract = service._authoritative_contract_row(
            opportunity,
            strategy.strategy_candidate_id,
        )

        assert strategy.strategy_candidate_id == "strategy-current"
        assert contract.contract_recommendation_id == "contract-current"
        assert contract.option_snapshot_id == "options-current"
        assert session.query(ContractRecommendationModel).count() == 3


def test_decision_result_exposes_unresolved_prerequisite_failures(monkeypatch):
    with Session(_engine()) as session:
        session.add(_opportunity("opp-unresolved"))
        session.commit()

        monkeypatch.setattr(
            "trading_ai.institutional_options.decision."
            "InstitutionalStrategyValuationService.value",
            lambda *_args, **_kwargs: StrategyValuationResult(
                requested=1,
                valued=0,
                selected=0,
                rejected=0,
                failed=1,
                errors=("opp-unresolved: ValueError: valuation failed",),
            ),
        )
        monkeypatch.setattr(
            "trading_ai.institutional_options.decision."
            "InstitutionalDynamicManagementService.generate",
            lambda *_args, **_kwargs: DynamicManagementResult(
                requested=1,
                created=0,
                failed=1,
                errors=("opp-unresolved: ValueError: management failed",),
            ),
        )

        result = InstitutionalDecisionService(session).build(
            opportunity_ids=("opp-unresolved",)
        )

        assert result.requested == 1
        assert result.prerequisite_requested == 1
        assert result.valuation_failed == 1
        assert result.management_failed == 1
        assert result.remaining_contracts_optimized == 1
        assert result.failed == 1
        assert any("valuation failed" in error for error in result.errors)
        assert any("management failed" in error for error in result.errors)


def test_static_recovery_contract_preserves_history_and_propagates_failures():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    management = (
        root / "src/trading_ai/institutional_options/management.py"
    ).read_text()
    valuation = (
        root / "src/trading_ai/institutional_options/valuation.py"
    ).read_text()
    decision = (
        root / "src/trading_ai/institutional_options/decision.py"
    ).read_text()

    assert "StrategyComparisonModel" in management
    assert "option_snapshot_id=option_snapshot_id" in management
    assert "Current governed option snapshot lineage is missing" in valuation
    assert "remaining_contracts_optimized" in decision
    assert "prerequisite_errors" in decision
    assert ".delete(" not in management
    assert ".delete(" not in valuation
