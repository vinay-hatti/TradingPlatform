from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from trading_ai.authoritative_paper_trading.database_models import PaperFillModel, PortfolioCashReservationModel
from trading_ai.authoritative_paper_trading.repositories import DatabaseOrderRepository
from trading_ai.authoritative_paper_trading.service import AuthoritativePaperAccountService
from trading_ai.database.base import Base
from trading_ai.order_management.order_profile import CanonicalOrderAggregate, CanonicalOrderLeg
from trading_ai.order_management.order_repository_exceptions import OptimisticConcurrencyError
from trading_ai.paper_trading.paper_execution_profile import PaperExecutionRecord, PaperFillProfile
from trading_ai.portfolio_management.database_models import PortfolioCashLedgerModel, PortfolioPositionModel


def factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def aggregate(version: int = 1, state: str = "CREATED") -> CanonicalOrderAggregate:
    return CanonicalOrderAggregate(
        aggregate_id="ORDER-1",
        client_order_id="CLIENT-1",
        account_id="PAPER-1",
        idempotency_key="IDEMPOTENCY-1",
        order_type="MARKET",
        time_in_force="DAY",
        legs=(CanonicalOrderLeg(
            leg_id="LEG-1", symbol="AAPL", asset_class="OPTION", side="BUY_TO_OPEN", quantity=2,
        ),),
        state=state,
        version=version,
        total_quantity=2,
        filled_quantity=0,
        remaining_quantity=2,
    )


def execution() -> PaperExecutionRecord:
    fill = PaperFillProfile(
        fill_id="FILL-1", execution_key="EXEC-1", aggregate_id="ORDER-1",
        client_order_id="CLIENT-1", leg_id="LEG-1", symbol="AAPL260821C00200000",
        side="BUY_TO_OPEN", quantity=2, fill_price=3.00, reference_price=2.95,
        slippage_amount=0.05, slippage_bps=169.49, commission=1.30, latency_ms=25,
        filled_at="2026-07-26T14:00:00+00:00",
    )
    return PaperExecutionRecord(
        execution_key="EXEC-1", session_id="SESSION-1", cycle_id="CYCLE-1",
        aggregate_id="ORDER-1", client_order_id="CLIENT-1", account_id="PAPER-1",
        order_type="MARKET", time_in_force="DAY", status="FILLED",
        requested_quantity=2, filled_quantity=2, remaining_quantity=0,
        average_fill_price=3.00, gross_value=600.0, commissions=1.30,
        net_cash_flow=-601.30, latency_ms=25, fills=(fill,),
        created_at="2026-07-26T14:00:00+00:00", updated_at="2026-07-26T14:00:00+00:00",
    )


def test_database_order_repository_preserves_contract_and_concurrency():
    session_factory = factory()
    with session_factory.begin() as session:
        repo = DatabaseOrderRepository(session)
        created = repo.create(aggregate())
        assert created.recommendation == "PERSISTED"
        assert repo.require("ORDER-1").legs[0].symbol == "AAPL"
        updated = replace(aggregate(), version=2, state="SUBMITTED")
        repo.save(updated, expected_version=1)
        assert repo.require("ORDER-1").state == "SUBMITTED"
        with pytest.raises(OptimisticConcurrencyError):
            repo.save(replace(updated, version=3, state="FILLED"), expected_version=1)


def test_transactional_settlement_is_idempotent_and_authoritative():
    session_factory = factory()
    service = AuthoritativePaperAccountService(session_factory)
    created = service.create_account(account_id="PAPER-1", name="Primary Paper Account", initial_capital=100_000)
    assert created["cash_balance"] == 100_000

    reservation = service.reserve_buying_power(account_id="PAPER-1", aggregate_id="ORDER-1", amount=700)
    assert reservation["status"] == "ACTIVE"
    assert service.account_summary("PAPER-1")["available_cash"] == 99_300

    result = service.settle_execution(execution(), asset_class="OPTION", multiplier=100)
    assert result["replayed"] is False
    assert result["cash_balance"] == 99_398.70
    assert result["reserved_cash"] == 0
    assert result["position_count"] == 1

    replay = service.settle_execution(execution(), asset_class="OPTION", multiplier=100)
    assert replay["replayed"] is True
    assert replay["cash_balance"] == result["cash_balance"]

    with session_factory() as session:
        assert session.scalar(select(PortfolioPositionModel).where(PortfolioPositionModel.position_id == "position-ORDER-1")) is not None
        assert len(session.scalars(select(PaperFillModel)).all()) == 1
        entries = session.scalars(select(PortfolioCashLedgerModel).order_by(PortfolioCashLedgerModel.occurred_at)).all()
        assert len(entries) == 2
        reservation_row = session.scalar(select(PortfolioCashReservationModel))
        assert reservation_row is not None and reservation_row.status == "CONSUMED"

    reconciliation = service.reconcile("PAPER-1")
    assert reconciliation["status"] == "READY"
    assert reconciliation["ledger_entries"] == 2


def test_runtime_checkpoint_and_trading_controls_use_database_adapters():
    from trading_ai.authoritative_paper_trading.repositories import (
        DatabasePaperAutomationRepository,
        DatabasePaperTradingRuntimeRepository,
        DatabaseTradingControlRepository,
    )
    from trading_ai.paper_trading.paper_automation_profile import PaperAutomationCheckpoint
    from trading_ai.paper_trading.paper_trading_profile import PaperTradingRuntimeState, PaperTradingSessionProfile
    from trading_ai.risk_gateway.trading_control_profile import KillSwitchProfile, TradingControlState

    session_factory = factory()
    with session_factory.begin() as session:
        runtime_repo = DatabasePaperTradingRuntimeRepository(session)
        state = PaperTradingRuntimeState(session=PaperTradingSessionProfile(
            session_id="SESSION-DB", account_id="PAPER-1", environment="PAPER",
            strategy_names=("LONG_CALL",), symbols=("AAPL",), cycle_interval_seconds=60,
            starting_capital=100_000,
        ))
        runtime_repo.save(state)
        assert runtime_repo.require("SESSION-DB").session.symbols == ("AAPL",)

        checkpoint_repo = DatabasePaperAutomationRepository(session)
        checkpoint = PaperAutomationCheckpoint(
            checkpoint_id="CP-1", session_id="SESSION-DB", cycle_id="CYCLE-1", stage="SCAN_DECISION",
        )
        checkpoint_repo.save(checkpoint)
        assert checkpoint_repo.get("CP-1").stage == "SCAN_DECISION"

        control_repo = DatabaseTradingControlRepository(session)
        control = TradingControlState(
            account_id="PAPER-1",
            kill_switch=KillSwitchProfile(account_id="PAPER-1", manual_active=True, reason="TEST"),
        )
        control_repo.save(control)
        loaded = control_repo.require("PAPER-1")
        assert loaded.kill_switch.active is True
        assert loaded.kill_switch.reason == "TEST"
