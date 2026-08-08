from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from trading_ai.database.base import Base
from trading_ai.broker.ibkr.database_models import (
    BrokerAccountBindingModel,
    BrokerAccountSnapshotModel,
    BrokerPositionSnapshotModel,
)
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel, BrokerPortfolioPublicationModel
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.portfolio_management.database_models import PortfolioAccountModel, PortfolioPositionModel


def factory(tmp_path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path/'m63.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def seed(Session):
    with Session() as s:
        s.add(PortfolioAccountModel(portfolio_id='PAPER-PRIMARY',name='Paper',base_currency='USD',initial_capital=100000,status='ACTIVE',created_at='2026-08-05T00:00:00+00:00',metadata_json={}))
        s.add(BrokerAccountBindingModel(binding_id='B1',portfolio_id='PAPER-PRIMARY',broker_name='INTERACTIVE_BROKERS',broker_environment='PAPER',broker_account_id='DU1234',base_currency='USD',host='127.0.0.1',port=7497,client_id=50,read_only=True,live_trading_enabled=False,status='VERIFIED_READ_ONLY',created_at='2026-08-05T00:00:00+00:00',updated_at='2026-08-05T00:00:00+00:00',metadata_json={}))
        s.add(BrokerAccountSnapshotModel(snapshot_id='S1',binding_id='B1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU1234',captured_at='2026-08-05T01:00:00+00:00',base_currency='USD',net_liquidation=100500,total_cash_value=90000,available_funds=80000,buying_power=200000,excess_liquidity=75000,raw_json={}))
        for cid,symbol,local in [(101,'WFC','WFC  260918C00070000'),(102,'USO','USO  260918C00085000'),(103,'XOM','XOM  260918C00120000')]:
            s.add(BrokerPositionSnapshotModel(snapshot_position_id=f'P{cid}',account_snapshot_id='S1',portfolio_id='PAPER-PRIMARY',broker_account_id='DU1234',contract_id=cid,symbol=symbol,local_symbol=local,security_type='OPT',currency='USD',exchange='SMART',quantity=1,average_cost=250,expiry='20260918',strike=70,right='C',multiplier=100,captured_at='2026-08-05T01:00:00+00:00',raw_json={}))
        s.commit()


def test_projects_broker_truth_into_portfolio_and_managed_positions(tmp_path):
    Session=factory(tmp_path);seed(Session)
    result=BrokerPortfolioSynchronizationService(Session).synchronize('PAPER-PRIMARY',connect_broker=False)
    assert result['broker_position_count']==3
    assert result['broker_discovered_positions']==3
    with Session() as s:
        assert len(s.scalars(select(BrokerCurrentPositionModel).where(BrokerCurrentPositionModel.active.is_(True))).all())==3
        assert len(s.scalars(select(PortfolioPositionModel).where(PortfolioPositionModel.status=='OPEN')).all())==3
        assert len(s.scalars(select(ManagedPositionModel).where(ManagedPositionModel.state=='OPEN')).all())==3
        assert s.scalar(select(BrokerPortfolioPublicationModel)) is not None


def test_sync_is_idempotent(tmp_path):
    Session=factory(tmp_path);seed(Session);svc=BrokerPortfolioSynchronizationService(Session)
    svc.synchronize('PAPER-PRIMARY',connect_broker=False);svc.synchronize('PAPER-PRIMARY',connect_broker=False)
    with Session() as s:
        assert len(s.scalars(select(BrokerCurrentPositionModel)).all())==3
        assert len(s.scalars(select(PortfolioPositionModel).where(PortfolioPositionModel.source_artifact=='M63_IBKR_BROKER_SYNC')).all())==3
        assert len(s.scalars(select(ManagedPositionModel)).all())==3


def test_release_files_reference_m63_operational_flow():
    root=Path(__file__).resolve().parents[2]
    assert 'brokerPortfolioApi' in (root/'ui/workstation/src/api.ts').read_text()
    assert 'Sync IBKR' in (root/'ui/workstation/src/PortfolioIntelligenceRefinedPage.tsx').read_text()
    assert (root/'scripts/run_m63_broker_portfolio_sync.py').exists()
    assert (root/'scripts/verify_m63_broker_portfolio_sync.py').exists()

def test_reconciliation_accepts_paper_trading_binding(tmp_path):
    Session=factory(tmp_path);seed(Session)
    with Session() as s:
        binding=s.get(BrokerAccountBindingModel,'B1');binding.status='VERIFIED_PAPER_TRADING';binding.read_only=False;s.commit()
    result=BrokerPortfolioSynchronizationService(Session).synchronize('PAPER-PRIMARY',connect_broker=False)
    assert result['broker_position_count']==3


def test_live_sync_uses_read_only_transport_without_downgrading_order_binding(tmp_path):
    from trading_ai.broker.ibkr.models import (
        IbkrAccountSummary,
        IbkrConnectionStatus,
        IbkrPositionSnapshot,
    )
    from trading_ai.broker.ibkr.service import IbkrPaperAccountService
    from trading_ai.broker.ibkr.transport import IbkrTransport

    class CapturingTransport(IbkrTransport):
        def __init__(self):
            self.config = None

        def connect(self, config):
            self.config = config
            assert config.read_only is True
            return IbkrConnectionStatus(
                connected=True,
                environment="PAPER",
                account_ids=("DU1234",),
                server_version=1,
                message="CONNECTED_READ_ONLY",
            )

        def disconnect(self):
            return None

        def account_summary(self, account_id):
            return IbkrAccountSummary(
                broker_account_id=account_id,
                base_currency="USD",
                net_liquidation=100000,
                total_cash_value=90000,
                available_funds=80000,
                buying_power=200000,
                excess_liquidity=75000,
                captured_at="2026-08-05T02:00:00+00:00",
                raw={},
            )

        def positions(self, account_id):
            return [
                IbkrPositionSnapshot(
                    broker_account_id=account_id,
                    contract_id=101,
                    symbol="WFC",
                    security_type="OPT",
                    currency="USD",
                    exchange="SMART",
                    quantity=1,
                    average_cost=250,
                    local_symbol="WFC  260918C00070000",
                    expiry="20260918",
                    strike=70,
                    right="C",
                    multiplier=100,
                    captured_at="2026-08-05T02:00:00+00:00",
                    raw={},
                )
            ]

    Session = factory(tmp_path)
    seed(Session)
    with Session() as s:
        binding = s.get(BrokerAccountBindingModel, "B1")
        binding.status = "VERIFIED_PAPER_TRADING"
        binding.read_only = False
        binding.live_trading_enabled = False
        s.commit()

    transport = CapturingTransport()
    result = IbkrPaperAccountService(Session, transport).verify_and_sync("PAPER-PRIMARY")
    assert result["status"] == "VERIFIED_PAPER_TRADING"
    assert transport.config.read_only is True
    with Session() as s:
        binding = s.get(BrokerAccountBindingModel, "B1")
        assert binding.status == "VERIFIED_PAPER_TRADING"
        assert binding.read_only is False
