from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from trading_ai.database.base import Base
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel, BrokerAccountSnapshotModel
from trading_ai.broker.ibkr.models import IbkrAccountSummary, IbkrConnectionStatus, IbkrPaperConnectionConfig, IbkrPositionSnapshot
from trading_ai.broker.ibkr.service import IbkrPaperAccountService
from trading_ai.broker.ibkr.transport import IbkrTransport


class FakeTransport(IbkrTransport):
    def connect(self, config):
        return IbkrConnectionStatus(True, "PAPER", (config.expected_account_id,))
    def disconnect(self):
        return None
    def account_summary(self, account_id):
        return IbkrAccountSummary(account_id, "USD", 125000.0, 50000.0, 45000.0, 180000.0)
    def positions(self, account_id):
        return [IbkrPositionSnapshot(account_id, 123, "SPY", "STK", "USD", "SMART", 10, 500.0, local_symbol="SPY")]


def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_config_rejects_non_paper_account():
    try:
        IbkrPaperConnectionConfig(expected_account_id="U123").validate()
    except ValueError as exc:
        assert "begin with DU" in str(exc)
    else:
        raise AssertionError("Non-paper account was accepted")


def test_register_is_idempotent_and_masks_account():
    sf = factory()
    service = IbkrPaperAccountService(sf)
    first = service.register(portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234567")
    second = service.register(portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234567")
    assert first["binding_id"] == second["binding_id"]
    assert first["broker_account_id_masked"] == "DU*****67"
    with sf() as session:
        assert len(session.scalars(select(BrokerAccountBindingModel)).all()) == 1


def test_verify_sync_activates_account_and_persists_snapshot():
    sf = factory()
    service = IbkrPaperAccountService(sf, FakeTransport())
    service.register(portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234567")
    result = service.verify_and_sync("PAPER-PRIMARY")
    assert result["status"] == "VERIFIED_READ_ONLY"
    assert result["positions_imported"] == 1
    assert result["live_trading_enabled"] is False
    with sf() as session:
        snapshot = session.scalar(select(BrokerAccountSnapshotModel))
        assert snapshot.net_liquidation == 125000.0
