from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from trading_ai.database.base import Base
from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerAccountSnapshotModel,
    BrokerReconciliationRunModel,
)
from trading_ai.broker.ibkr.models import (
    IbkrAccountSummary,
    IbkrConnectionStatus,
    IbkrPositionSnapshot,
)
from trading_ai.broker.ibkr.reconciliation import IbkrPaperReconciliationService
from trading_ai.broker.ibkr.service import IbkrPaperAccountService
from trading_ai.broker.ibkr.transport import IbkrTransport
from trading_ai.portfolio_management.database_models import PortfolioPositionModel


class FakeReadOnlyTransport(IbkrTransport):
    def connect(self, config):
        return IbkrConnectionStatus(True, "PAPER", (config.expected_account_id,), 188, "CONNECTED_READ_ONLY")

    def disconnect(self):
        return None

    def account_summary(self, account_id):
        return IbkrAccountSummary(
            account_id,
            "USD",
            150000.0,
            80000.0,
            75000.0,
            300000.0,
            70000.0,
            raw={"source": "fake"},
        )

    def positions(self, account_id):
        return [
            IbkrPositionSnapshot(
                account_id,
                111,
                "SPY",
                "STK",
                "USD",
                "SMART",
                10,
                500.0,
                local_symbol="SPY",
            ),
            IbkrPositionSnapshot(
                account_id,
                222,
                "AAPL",
                "OPT",
                "USD",
                "SMART",
                -2,
                350.0,
                local_symbol="AAPL  260821P00200000",
                expiry="20260821",
                strike=200.0,
                right="P",
                multiplier=100.0,
            ),
        ]


def factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_verify_sync_is_read_only_and_persists_broker_snapshot():
    sf = factory()
    service = IbkrPaperAccountService(sf, FakeReadOnlyTransport())
    service.register(portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234567")
    result = service.verify_and_sync("PAPER-PRIMARY")
    assert result["status"] == "VERIFIED_READ_ONLY"
    assert result["positions_imported"] == 2
    assert result["live_trading_enabled"] is False
    with sf() as session:
        binding = session.scalar(select(BrokerAccountBindingModel))
        snapshot = session.scalar(select(BrokerAccountSnapshotModel))
        assert binding.status == "VERIFIED_READ_ONLY"
        assert binding.read_only is True
        assert snapshot.net_liquidation == 150000.0


def test_reconciliation_imports_broker_positions_into_authoritative_ledger():
    sf = factory()
    service = IbkrPaperAccountService(sf, FakeReadOnlyTransport())
    service.register(portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234567")
    service.verify_and_sync("PAPER-PRIMARY")
    result = IbkrPaperReconciliationService(sf).reconcile("PAPER-PRIMARY")
    assert result["positions_imported"] == 2
    assert result["position_difference_count"] == 2
    with sf() as session:
        positions = list(session.scalars(select(PortfolioPositionModel)).all())
        run = session.scalar(select(BrokerReconciliationRunModel))
        assert len(positions) == 2
        assert {p.direction for p in positions} == {"LONG", "SHORT"}
        assert all(p.source_artifact == "IBKR_PAPER_SYNC" for p in positions)
        assert run.status == "RECONCILED_WITH_DIFFERENCES"


def test_second_reconciliation_is_idempotent():
    sf = factory()
    service = IbkrPaperAccountService(sf, FakeReadOnlyTransport())
    service.register(portfolio_id="PAPER-PRIMARY", broker_account_id="DU1234567")
    service.verify_and_sync("PAPER-PRIMARY")
    reconciliation = IbkrPaperReconciliationService(sf)
    reconciliation.reconcile("PAPER-PRIMARY")
    second = reconciliation.reconcile("PAPER-PRIMARY")
    assert second["positions_imported"] == 0
    assert second["position_difference_count"] == 0
    with sf() as session:
        assert len(session.scalars(select(PortfolioPositionModel)).all()) == 2
