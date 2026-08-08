from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.institutional_options.handoff import InstitutionalOptionsHandoffService
from trading_ai.institutional_options.models import (
    ContractRecommendationModel, ExecutionRecommendationModel,
    InstitutionalOptionHandoffModel, InstitutionalOpportunityModel,
    OpportunityThesisModel, PositionManagementSnapshotModel,
    StrategyCandidateModel, StrategyComparisonModel, StrategyValuationModel,
)


def seed(session: Session) -> None:
    session.add(InstitutionalOpportunityModel(
        opportunity_id="opp-1", symbol="AAPL", asset_class="EQUITY", state="CONTRACTS_OPTIMIZED",
        direction="BULLISH", category="TREND_CONTINUATION", overall_score=90, confidence=87,
        conviction="HIGH", thesis_id="thesis-1", stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id="stock-run-1", stock_candidate_id="stock-candidate-1",
        stock_state_hash="state-hash-1", option_snapshot_id="options-snap-1", version=3,
        created_at="2026-08-04T00:00:00+00:00", updated_at="2026-08-04T00:00:00+00:00",
        payload_json={"lineage":{"source_provider":"POLYGON_PERSISTED"}},
    ))
    session.add(OpportunityThesisModel(
        thesis_id="thesis-1", opportunity_id="opp-1", direction="BULLISH",
        setup_category="TREND_CONTINUATION", primary_timeframe="1d", invalidation_level=195,
        entry_zone_low=199, entry_zone_high=200, created_at="2026-08-04T00:00:00+00:00",
        payload_json={"targets":[208,212],"evidence":["Weekly trend aligned"],"risks":["Resistance nearby"]},
    ))
    session.add(StrategyCandidateModel(
        strategy_candidate_id="strategy-1", opportunity_id="opp-1", strategy="BULL_CALL_SPREAD",
        disposition="SELECTED", eligibility_score=91, strategy_score=94, complexity="LOW", rank=1,
        selected=True, payload_json={"selected":True},
    ))
    session.add(StrategyComparisonModel(
        comparison_id="comparison-1", opportunity_id="opp-1", selected_strategy_candidate_id="strategy-1",
        policy_version="m62-v1", created_at="2026-08-04T00:00:00+00:00", payload_json={},
    ))
    session.add(ContractRecommendationModel(
        contract_recommendation_id="contract-1", opportunity_id="opp-1", strategy_candidate_id="strategy-1",
        option_snapshot_id="options-snap-1", executable=True, liquidity_score=93,
        created_at="2026-08-04T00:00:00+00:00",
        payload_json={"legs":[
            {"leg_id":"l1","side":"BUY","option_type":"CALL","option_symbol":"O:AAPL260918C00200000","expiry":"2026-09-18","strike":200,"quantity_ratio":1,"bid":5.0,"ask":5.2,"delta":.55,"gamma":.02,"theta":-.04,"vega":.12},
            {"leg_id":"l2","side":"SELL","option_type":"CALL","option_symbol":"O:AAPL260918C00210000","expiry":"2026-09-18","strike":210,"quantity_ratio":1,"bid":2.0,"ask":2.2,"delta":.30,"gamma":.01,"theta":-.02,"vega":.08},
        ]},
    ))
    session.add(StrategyValuationModel(
        valuation_id="valuation-1", opportunity_id="opp-1", strategy_candidate_id="strategy-1",
        strategy_score=94, calibrated_probability=.72, expected_value=320, expected_return_on_risk=.45,
        selected=True, created_at="2026-08-04T00:00:00+00:00", payload_json={},
    ))
    session.add(ExecutionRecommendationModel(
        execution_recommendation_id="execution-1", opportunity_id="opp-1",
        strategy_candidate_id="strategy-1", contract_recommendation_id="contract-1",
        underlying_stop=195, trailing_policy="UNDERLYING_HIGHER_LOW", ready_for_trade_builder=True,
        created_at="2026-08-04T00:00:00+00:00",
        payload_json={"underlying_targets":[208,212],"emergency_option_stop_pct":.45,"theta_exit_days_to_expiry":10,"volatility_exit_rule":"EXIT_ON_IV_COLLAPSE"},
    ))
    session.add(PositionManagementSnapshotModel(
        management_snapshot_id="management-1", opportunity_id="opp-1", strategy_candidate_id="strategy-1",
        thesis_integrity=.88, position_health=.91, action="HOLD", trailing_policy="UNDERLYING_HIGHER_LOW",
        created_at="2026-08-04T00:00:00+00:00", payload_json={},
    ))
    session.flush()


def session_with_seed():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed(session)
    return session


def test_handoff_creates_exact_trade_plan_and_lineage():
    with session_with_seed() as session:
        result = InstitutionalOptionsHandoffService(session).create_trade_plan(
            "opp-1", account_id="PAPER-PRIMARY", capital=100000, risk_budget_pct=1, actor="tester"
        )
        plan = session.get(TradePlanModel, result.trade_plan_id)
        assert plan is not None and plan.state == "VALIDATED"
        assert [x["option_symbol"] for x in plan.legs_json] == ["O:AAPL260918C00200000", "O:AAPL260918C00210000"]
        assert plan.execution_intent_json["m62_lineage"]["stock_state_hash"] == "state-hash-1"
        assert plan.execution_intent_json["dynamic_management"]["underlying_stop"] == 195
        assert session.query(InstitutionalOptionHandoffModel).count() == 1


def test_handoff_is_idempotent_for_same_source():
    with session_with_seed() as session:
        service = InstitutionalOptionsHandoffService(session)
        first = service.create_trade_plan("opp-1", account_id="PAPER-PRIMARY", capital=100000, risk_budget_pct=1, actor="tester")
        second = service.create_trade_plan("opp-1", account_id="PAPER-PRIMARY", capital=100000, risk_budget_pct=1, actor="tester")
        assert first.trade_plan_id == second.trade_plan_id
        assert session.query(TradePlanModel).count() == 1


def test_limit_price_override_is_governed():
    with session_with_seed() as session:
        try:
            InstitutionalOptionsHandoffService(session).create_trade_plan(
                "opp-1", account_id="PAPER-PRIMARY", capital=100000, risk_budget_pct=1, actor="tester",
                overrides={"limit_prices":{"O:AAPL260918C00200000":9.0}},
            )
        except ValueError as exc:
            assert "deviation" in str(exc)
        else:
            raise AssertionError("Expected governed override rejection")


def test_execution_intent_preserves_m62_metadata():
    with session_with_seed() as session:
        service = InstitutionalOptionsHandoffService(session)
        handoff = service.create_trade_plan("opp-1", account_id="PAPER-PRIMARY", capital=100000, risk_budget_pct=1, actor="tester")
        plan = session.get(TradePlanModel, handoff.trade_plan_id)
        plan.state = "PAPER_READY"
        session.commit()
        result = service.create_execution_intent(handoff.handoff_id, actor="tester")
        intent = session.get(ExecutionIntentModel, result.execution_intent_id)
        assert intent.metadata_json["source"] == "M62_INSTITUTIONAL_OPTIONS"
        assert intent.metadata_json["m62_lineage"]["contract_recommendation_id"] == "contract-1"
        assert intent.metadata_json["dynamic_management"]["underlying_targets"] == [208, 212]


def test_handoff_routes_and_ui_action_registered():
    from pathlib import Path
    router = Path("src/trading_ai/institutional_options/router.py").read_text()
    page = Path("ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    assert '/handoff/trade-builder' in router
    assert '/execution-intent' in router
    assert 'Create Trade Plan' in page
    assert "Daily scanner" in Path("ui/workstation/src/pages.tsx").read_text()
    assert "Option scanner" in Path("ui/workstation/src/pages.tsx").read_text()
