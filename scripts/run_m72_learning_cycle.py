#!/usr/bin/env python3
import argparse, json
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.performance_learning.continuous_learning import ContinuousLearningService


def sync_ibkr_execution_history(portfolio_id: str) -> dict:
    """Explicit, operator-requested IBKR paper synchronization.

    Continuous learning never opens a broker connection by default. This switch is
    available when the operator wants to import current order statuses/executions
    before rebuilding execution-learning evidence.
    """
    from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel
    from trading_ai.broker.ibkr.models import IbkrPaperConnectionConfig
    from trading_ai.broker.ibkr.order_service import IbkrPaperOrderService
    from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport

    with SessionLocal() as s:
        binding = s.scalar(select(BrokerAccountBindingModel).where(
            BrokerAccountBindingModel.portfolio_id == portfolio_id,
            BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS",
        ))
        if binding is None:
            raise KeyError(f"IBKR binding not found for {portfolio_id}")
        config = IbkrPaperConnectionConfig(
            host=binding.host,
            port=binding.port,
            client_id=binding.client_id,
            environment="PAPER",
            expected_account_id=binding.broker_account_id,
            timeout_seconds=15,
            read_only=False,
        )
    transport = IbapiPaperOrderTransport()
    try:
        transport.connect(config)
        return IbkrPaperOrderService(SessionLocal, transport).synchronize(portfolio_id)
    finally:
        transport.disconnect()


def main():
    p=argparse.ArgumentParser(description='Run governed prediction/outcome/calibration learning cycle')
    p.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    p.add_argument('--dashboard',action='store_true')
    p.add_argument('--sync-ibkr',action='store_true',help='Explicitly synchronize IBKR paper order statuses/executions before rebuilding learning evidence')
    a=p.parse_args()
    broker_sync=None
    if a.sync_ibkr:
        broker_sync=sync_ibkr_execution_history(a.portfolio_id)
    with SessionLocal() as s:
        svc=ContinuousLearningService(s)
        result=svc.dashboard(a.portfolio_id) if a.dashboard else svc.run_cycle(a.portfolio_id)
    if broker_sync is not None and isinstance(result,dict):
        result={"broker_sync":broker_sync,**result}
    print(json.dumps(result,indent=2,default=str))
    return 0
if __name__=='__main__':raise SystemExit(main())
