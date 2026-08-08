from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.database.base import Base
from trading_ai.execution_workspace.models import (
    ExecutionIntentAuditModel,
    ExecutionIntentModel,
)
from trading_ai.execution_workspace.service import ExecutionWorkspaceService


def test_management_refresh_advances_version_before_audit():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    plan = TradePlanModel(
        trade_plan_id="TP-M62-REFRESH",
        opportunity_id="opp-refresh",
        opportunity_version=1,
        intelligence_id="state-hash",
        account_id="PAPER-PRIMARY",
        symbol="TEST",
        direction="BULLISH",
        strategy="LONG_CALL",
        state="PAPER_READY",
        version=3,
        capital=100000,
        risk_budget_pct=1,
        risk_budget_amount=1000,
        estimated_debit=500,
        estimated_credit=0,
        max_loss=500,
        max_profit=None,
        reward_risk_ratio=None,
        net_greeks_json={},
        validation_json={"valid": True, "defined_risk": True},
        legs_json=[],
        execution_intent_json={
            "decision_snapshot_id": "decision-1",
            "decision_state_hash": "hash-2",
            "dynamic_management": {
                "underlying_stop": 95,
                "underlying_targets": [110, 120],
            },
        },
        notes="M62",
        created_by="test",
        created_at="2026-08-04T00:00:00+00:00",
        updated_at="2026-08-04T00:00:00+00:00",
    )
    intent = ExecutionIntentModel(
        execution_intent_id="XI-REFRESH",
        trade_plan_id=plan.trade_plan_id,
        trade_plan_version=plan.version,
        opportunity_id=plan.opportunity_id,
        portfolio_id="PAPER-PRIMARY",
        account_id="PAPER-PRIMARY",
        symbol="TEST",
        strategy="LONG_CALL",
        state="VALIDATED",
        version=1,
        max_loss=500,
        legs_json=[],
        order_request_json={},
        validation_json={"valid": True},
        broker_json={},
        metadata_json={"paper_only": True, "dynamic_management": {}},
        created_by="test",
        created_at="2026-08-04T00:00:00+00:00",
        updated_at="2026-08-04T00:00:00+00:00",
        submitted_at=None,
        terminal_at=None,
    )
    audit = ExecutionIntentAuditModel(
        event_id="XEA-CREATED",
        execution_intent_id=intent.execution_intent_id,
        execution_intent_version=1,
        event_type="EXECUTION_INTENT_CREATED",
        previous_state=None,
        new_state="VALIDATED",
        actor="test",
        reason="created",
        event_timestamp="2026-08-04T00:00:00+00:00",
        payload_json={},
    )

    with Session(engine) as session:
        session.add_all([plan, intent, audit])
        session.commit()

        result = ExecutionWorkspaceService(session).create_from_trade_plan(
            plan.trade_plan_id, "test"
        )

        assert result["version"] == 2
        refreshed = session.get(ExecutionIntentModel, "XI-REFRESH")
        assert refreshed.version == 2
        assert refreshed.metadata_json["dynamic_management"]["underlying_stop"] == 95

        events = list(
            session.scalars(
                select(ExecutionIntentAuditModel)
                .where(ExecutionIntentAuditModel.execution_intent_id == "XI-REFRESH")
                .order_by(ExecutionIntentAuditModel.execution_intent_version)
            )
        )
        assert [event.execution_intent_version for event in events] == [1, 2]
        assert events[-1].event_type == "EXECUTION_INTENT_MANAGEMENT_REFRESHED"
