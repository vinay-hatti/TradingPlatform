from __future__ import annotations
import json
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel, BrokerOrderModel
from trading_ai.broker.ibkr.models import IbkrPaperConnectionConfig
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport


def main():
    with SessionLocal() as s:
        binding=s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id=='PAPER-PRIMARY',BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
        if not binding: raise SystemExit('IBKR PAPER-PRIMARY binding not found')
        rows=list(s.scalars(select(BrokerOrderModel).where(BrokerOrderModel.status=='REJECTED',BrokerOrderModel.last_error.ilike('%minimum price variation%')).order_by(BrokerOrderModel.submitted_at.desc()).limit(10)))
        transport=IbapiPaperOrderTransport()
        try:
            transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False))
            output=[]
            for row in rows:
                raw=dict(row.raw_json or {}); req=dict(raw.get('request') or {})
                contract_id=int(req.get('contract_id') or 0); requested=float(row.limit_price or req.get('limit_price') or 0.0); side=str(row.side or req.get('side') or 'BUY'); exchange=str(req.get('exchange') or 'SMART')
                if contract_id<=0 or requested<=0: continue
                norm=transport.normalize_option_limit_price(contract_id=contract_id,price=requested,side=side,exchange=exchange)
                output.append({'symbol':row.symbol,'broker_order_id':row.broker_order_id,'contract_id':contract_id,'requested_price':requested,**norm})
            print(json.dumps({'version':'M73.0.5-ENTRY-IBKR-MINIMUM-TICK-NORMALIZATION-1.0','rows':output},indent=2))
        finally:
            transport.disconnect()

if __name__=='__main__':main()
