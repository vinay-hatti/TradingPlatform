from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.autonomous_position_management.models import M73PositionManagerModel
from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerAccountSnapshotModel,
    BrokerPositionSnapshotModel,
)
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel, BrokerPortfolioAlertModel
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.database.base import Base
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.portfolio_management.database_models import PortfolioAccountModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TS = "2026-08-10T18:13:55+00:00"
CONTRACT_ID = 787047242
LOCAL_SYMBOL = "TJX   260918C00160000"
CANONICAL_ID = "POS-TJX-CANONICAL"
DUPLICATE_ID = "MP-IBKR-TJX-DUPLICATE"
TRADE_PLAN_ID = "TP-TJX-1"


def factory(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path/'m731.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def seed_tjx_duplicate_case(Session):
    dynamic_management = {
        "underlying_stop": 154.131,
        "underlying_targets": [163.6731, 165.0, 169.6557],
        "theta_exit_days_to_expiry": 10,
        "volatility_exit_rule": "EXIT_OR_REDUCE_ON_IV_COLLAPSE_WITH_THESIS_DETERIORATION",
        "emergency_option_stop_pct": 0.55,
    }
    with Session() as s:
        s.add(PortfolioAccountModel(portfolio_id="PAPER-PRIMARY", name="Paper", base_currency="USD", initial_capital=100000, status="ACTIVE", created_at=TS, metadata_json={}))
        s.add(BrokerAccountBindingModel(binding_id="B1", portfolio_id="PAPER-PRIMARY", broker_name="INTERACTIVE_BROKERS", broker_environment="PAPER", broker_account_id="DU1234", base_currency="USD", host="127.0.0.1", port=7497, client_id=50, read_only=False, live_trading_enabled=False, status="VERIFIED_PAPER_TRADING", created_at=TS, updated_at=TS, metadata_json={}))
        s.add(BrokerAccountSnapshotModel(snapshot_id="S1", binding_id="B1", portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234", captured_at=TS, base_currency="USD", net_liquidation=100000, total_cash_value=90000, available_funds=80000, buying_power=200000, excess_liquidity=75000, raw_json={}))
        s.add(BrokerPositionSnapshotModel(snapshot_position_id="PS1", account_snapshot_id="S1", portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234", contract_id=CONTRACT_ID, symbol="TJX", local_symbol=LOCAL_SYMBOL, security_type="OPT", currency="USD", exchange="SMART", quantity=1, average_cost=570.0, expiry="20260918", strike=160.0, right="C", multiplier=100, captured_at=TS, raw_json={}))
        s.add(TradePlanModel(
            trade_plan_id=TRADE_PLAN_ID, opportunity_id="OP-TJX", opportunity_version=1, intelligence_id=None,
            account_id="PAPER-PRIMARY", symbol="TJX", direction="BULLISH", strategy="LONG_CALL", state="PAPER_READY", version=1,
            capital=10000, risk_budget_pct=1, risk_budget_amount=100, estimated_debit=5.7, estimated_credit=0,
            max_loss=570, max_profit=None, reward_risk_ratio=None, net_greeks_json={}, validation_json={},
            legs_json=[{"option_symbol": "O:TJX260918C00160000", "expiry": "2026-09-18", "strike": 160.0, "option_right": "CALL", "side": "BUY", "quantity": 1}],
            execution_intent_json={"dynamic_management": dynamic_management}, notes="", created_by="test", created_at=TS, updated_at=TS,
        ))
        # Original position created by Execution Workspace at fill. It intentionally lacks
        # broker_contract_id, reproducing the production identity gap.
        s.add(ManagedPositionModel(
            position_id=CANONICAL_ID, portfolio_id="PAPER-PRIMARY", trade_plan_id=TRADE_PLAN_ID, opportunity_id="OP-TJX",
            intelligence_id=None, execution_id="XI-TJX", symbol="TJX", strategy="LONG_CALL", direction="BULLISH", state="OPEN",
            version=2, opened_at=TS, closed_at=None, entry_value=570, realized_pnl=0,
            mark_json={"mark_price": 5.7, "quantity": 0.0, "market_value": 0.0, "unrealized_pnl": 0.0, "unrealized_return_pct": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "days_to_expiry": None},
            health_json={}, decision_json={}, metadata_json={"automation_mode": "FULLY_AUTOMATIC", "management_mode": "PLATFORM_MANAGED", "dynamic_management": dynamic_management},
            created_by="test", created_at=TS, updated_at=TS,
        ))
        s.add(M73PositionManagerModel(manager_id="MGR-CANONICAL", position_id=CANONICAL_ID, portfolio_id="PAPER-PRIMARY", state="ACTIVE", automation_mode="FULLY_AUTOMATIC", protection_state="UNPROTECTED", heartbeat_at=TS, activated_at=TS, recovered_at=None, last_decision="HOLD", conviction_score=50, thesis_integrity=.5, metadata_json={"active_instruction_count": 0}))
        # Historical instructions were cancelled when the original record temporarily resolved
        # to quantity zero. They must remain history, while a new active generation is re-armed.
        s.add(PositionExitInstructionModel(instruction_id="PXI-OLD-STOP", assessment_id="A1", position_id=CANONICAL_ID, action="CLOSE", quantity=0, status="CANCELLED", payload={"label": "STRUCTURAL_STOP", "cancel_reason": "NO_REMAINING_BROKER_QUANTITY"}, created_at=TS))
        # Duplicate broker-discovered projection currently owning broker_current_positions.
        s.add(ManagedPositionModel(
            position_id=DUPLICATE_ID, portfolio_id="PAPER-PRIMARY", trade_plan_id=f"BROKER-DISCOVERED:{CONTRACT_ID}", opportunity_id=f"BROKER-DISCOVERED:{CONTRACT_ID}",
            intelligence_id=None, execution_id=None, symbol="TJX", strategy="BROKER_DISCOVERED", direction="BULLISH", state="OPEN",
            version=1, opened_at=TS, closed_at=None, entry_value=570, realized_pnl=0,
            mark_json={"mark_price": 5.7, "quantity": 1.0, "market_value": 570.0, "unrealized_pnl": 0.0, "unrealized_return_pct": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "days_to_expiry": None},
            health_json={}, decision_json={}, metadata_json={"broker_contract_id": str(CONTRACT_ID), "broker_discovered": True, "automation_mode": "ADVISORY"},
            created_by="test", created_at=TS, updated_at=TS,
        ))
        s.add(M73PositionManagerModel(manager_id="MGR-DUP", position_id=DUPLICATE_ID, portfolio_id="PAPER-PRIMARY", state="ACTIVE", automation_mode="ADVISORY", protection_state="UNPROTECTED", heartbeat_at=TS, activated_at=TS, recovered_at=None, last_decision="REDUCE", conviction_score=50, thesis_integrity=.5, metadata_json={}))
        s.add(BrokerCurrentPositionModel(
            broker_position_id="BCP-TJX", portfolio_id="PAPER-PRIMARY", binding_id="B1", broker_account_id="DU1234", account_snapshot_id="S1",
            contract_id=CONTRACT_ID, symbol="TJX", local_symbol=LOCAL_SYMBOL, security_type="OPT", currency="USD", exchange="SMART",
            signed_quantity=1.0, average_cost=5.7, market_price=5.7, market_value=570.0, unrealized_pnl=0.0, realized_pnl=0.0,
            expiry="20260918", strike=160.0, right="C", multiplier=100, active=True, provenance="BROKER_DISCOVERED", reconciliation_status="BROKER_DISCOVERED",
            portfolio_position_id=None, managed_position_id=DUPLICATE_ID, first_seen_at=TS, last_seen_at=TS, closed_at=None, raw_json={},
        ))
        s.add(BrokerPortfolioAlertModel(
            alert_id="ALERT-TJX-DISCOVERED", portfolio_id="PAPER-PRIMARY", broker_position_id="BCP-TJX",
            severity="WARNING", alert_type="BROKER_DISCOVERED_POSITION", status="OPEN",
            message="Position exists at IBKR without complete platform decision lineage", created_at=TS, resolved_at=None, payload_json={},
        ))
        s.commit()


def test_trade_plan_contract_identity_converges_duplicate_and_rearms_management(tmp_path):
    Session = factory(tmp_path)
    seed_tjx_duplicate_case(Session)
    result = BrokerPortfolioSynchronizationService(Session).synchronize("PAPER-PRIMARY", connect_broker=False)
    assert result["matched_positions"] == 1

    with Session() as s:
        broker = s.get(BrokerCurrentPositionModel, "BCP-TJX")
        assert broker.managed_position_id == CANONICAL_ID
        assert broker.provenance == "INSTITUTIONAL_OPTIONS"
        assert (broker.raw_json or {}).get("lineage", {}).get("identity_match") == "OCC_OPTION_SYMBOL"

        canonical = s.get(ManagedPositionModel, CANONICAL_ID)
        assert canonical.state == "OPEN"
        assert float(canonical.mark_json["quantity"]) == 1.0
        assert canonical.metadata_json["broker_contract_id"] == str(CONTRACT_ID)

        duplicate = s.get(ManagedPositionModel, DUPLICATE_ID)
        assert duplicate.state == "SUPERSEDED"
        assert duplicate.metadata_json["superseded_by_managed_position_id"] == CANONICAL_ID
        duplicate_manager = s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id == DUPLICATE_ID))
        assert duplicate_manager.state == "SUPERSEDED"

        canonical_manager = s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id == CANONICAL_ID))
        assert canonical_manager.automation_mode == "FULLY_AUTOMATIC"
        assert canonical_manager.state == "ACTIVE"
        assert canonical_manager.metadata_json["last_rearmed_reason"] == "OPEN_BROKER_QUANTITY_WITHOUT_ACTIVE_EXIT_INSTRUCTIONS"

        instructions = list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id == CANONICAL_ID)).all())
        assert any(x.status == "CANCELLED" and x.instruction_id == "PXI-OLD-STOP" for x in instructions)
        active = [x for x in instructions if x.status == "ARMED"]
        assert active
        assert any((x.payload or {}).get("label") == "STRUCTURAL_STOP" for x in active)
        assert all(x.quantity > 0 for x in active)

        alert = s.get(BrokerPortfolioAlertModel, "ALERT-TJX-DISCOVERED")
        assert alert.status == "RESOLVED"
        assert alert.resolved_at
        assert alert.payload_json["resolved_managed_position_id"] == CANONICAL_ID


def test_contract_helper_matches_real_polygon_option_symbol_to_ibkr_local_symbol():
    class TP:
        symbol = "TJX"
        legs_json = [{"option_symbol": "O:TJX260918C00160000", "expiry": "2026-09-18", "strike": 160.0, "option_right": "CALL"}]
    class Broker:
        contract_id = 787047242
        local_symbol = "TJX   260918C00160000"
        symbol = "TJX"
        expiry = "20260918"
        strike = 160.0
        right = "C"
    assert BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(TP(), Broker()) == "OCC_OPTION_SYMBOL"
    assert BrokerPortfolioSynchronizationService._trade_plan_matches_broker_contract(TP(), Broker())


def test_contract_helper_uses_full_tuple_only_and_rejects_near_miss():
    class TP:
        symbol = "TJX"
        legs_json = [{"expiry": "2026-09-18", "strike": 160.0, "option_right": "CALL"}]
    class Broker:
        contract_id = 1
        local_symbol = ""
        symbol = "TJX"
        expiry = "20260918"
        strike = 160.0
        right = "C"
    assert BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(TP(), Broker()) == "OPTION_TUPLE"
    Broker.strike = 165.0
    assert BrokerPortfolioSynchronizationService._trade_plan_broker_identity_match(TP(), Broker()) is None
