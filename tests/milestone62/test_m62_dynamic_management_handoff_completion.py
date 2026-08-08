from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.advanced_trade_builder.service import AdvancedTradeBuilderService
from trading_ai.database.base import Base


def _plan() -> TradePlanModel:
    return TradePlanModel(
        trade_plan_id="TP-M62-MGMT",
        opportunity_id="opp-mgmt",
        opportunity_version=1,
        intelligence_id="state-hash",
        account_id="PAPER-PRIMARY",
        symbol="TEST",
        direction="BULLISH",
        strategy="LONG_CALL",
        state="APPROVED",
        version=1,
        capital=100000,
        risk_budget_pct=1,
        risk_budget_amount=1000,
        estimated_debit=500,
        estimated_credit=0,
        max_loss=500,
        max_profit=None,
        reward_risk_ratio=None,
        net_greeks_json={},
        validation_json={"valid": True},
        legs_json=[{
            "side": "BUY", "quantity": 1, "option_right": "CALL",
            "strike": 100, "expiry": "2026-09-18", "limit_price": 5,
            "option_symbol": "O:TEST260918C00100000",
            "delta": .5, "gamma": .1, "theta": -.1, "vega": .2,
        }],
        execution_intent_json={
            "decision_snapshot_id": "decision-1",
            "decision_state_hash": "hash-1",
            "dynamic_management": {
                "underlying_stop": 95,
                "underlying_targets": [110, 120],
                "trailing_policy": "UNDERLYING_HIGHER_LOW",
            },
        },
        notes="M62",
        created_by="test",
        created_at="2026-08-04T00:00:00+00:00",
        updated_at="2026-08-04T00:00:00+00:00",
    )


def test_paper_ready_transition_preserves_m62_management_payload():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        plan = _plan()
        session.add(plan)
        session.commit()
        result = AdvancedTradeBuilderService(session).transition(
            plan.trade_plan_id, 1, "PAPER_READY", "test", "ready"
        )
        assert result.execution_intent["decision_snapshot_id"] == "decision-1"
        assert result.execution_intent["dynamic_management"]["underlying_stop"] == 95
        assert result.execution_intent["submission_status"] == "READY_FOR_EXISTING_ROUTER"


def test_ui_exposes_dynamic_management_and_nonempty_actions():
    root = Path(__file__).resolve().parents[2]
    execution = (root / "ui/workstation/src/ExecutionWorkspacePage.tsx").read_text()
    builder = (root / "ui/workstation/src/AdvancedTradeBuilderPage.tsx").read_text()
    institutional = (root / "ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    for text in (
        "Dynamic management & exit plan",
        "Structural stop",
        "Emergency option stop",
        "Platform managed after fill",
    ):
        assert text.lower() in execution.lower()
    assert "Review validation" in builder
    assert "Institutional management handoff" in builder
    assert "load(true)" in institutional


def test_fill_activation_persists_managed_exit_instructions_source_contract():
    root = Path(__file__).resolve().parents[2]
    service = (root / "src/trading_ai/execution_workspace/service.py").read_text()
    portfolio = (root / "src/trading_ai/portfolio_intelligence/service.py").read_text()
    assert "_activate_exit_instructions" in service
    assert "PositionExitInstructionModel" in service
    for label in (
        "STRUCTURAL_STOP", "THETA_EXIT",
        "VOLATILITY_EXIT", "EMERGENCY_OPTION_STOP",
    ):
        assert label in service
    assert "f'TARGET_{index}'" in service
    assert "dynamic_management" in portfolio
    assert "management_mode':'PLATFORM_MANAGED'" in portfolio
