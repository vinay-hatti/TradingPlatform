from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import select

from trading_ai.autonomous_position_management.models import M73PositionManagerModel
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TERMINAL_INSTRUCTIONS={"FILLED","CANCELLED","CANCELED","REJECTED","FAILED","SUPERSEDED","COMPLETED"}


def audit(portfolio_id: str) -> dict:
    rows=[]
    with SessionLocal() as s:
        broker=list(s.scalars(select(BrokerCurrentPositionModel).where(
            BrokerCurrentPositionModel.portfolio_id==portfolio_id,
            BrokerCurrentPositionModel.active.is_(True),
        )).all())
        seen_positions=set()
        for br in broker:
            pid=br.managed_position_id
            managed=s.get(ManagedPositionModel,pid) if pid else None
            manager=s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id==pid)) if pid else None
            instructions=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==pid)).all()) if pid else []
            active=[x for x in instructions if str(x.status or '').upper() not in TERMINAL_INSTRUCTIONS]
            status='PASS_ARMED'
            if not pid:status='FAIL_NO_MANAGED_POSITION'
            elif managed is None:status='FAIL_MANAGED_POSITION_NOT_FOUND'
            elif bool((managed.metadata_json or {}).get('broker_discovered')) or str(managed.trade_plan_id or '').startswith('BROKER-DISCOVERED:'):status='FAIL_BROKER_DISCOVERED'
            elif manager is None:status='FAIL_NO_MANAGER'
            elif str(manager.state or '').upper()!='ACTIVE':status='FAIL_MANAGER_NOT_ACTIVE'
            elif str(manager.automation_mode or '').upper()!='FULLY_AUTOMATIC':status='FAIL_NOT_FULLY_AUTOMATIC'
            elif not active:status='FAIL_NO_ACTIVE_EXITS'
            rows.append({
                'symbol':br.symbol,'contract_id':br.contract_id,'local_symbol':br.local_symbol,'signed_quantity':br.signed_quantity,
                'managed_position_id':pid,'managed_strategy':managed.strategy if managed else None,'trade_plan_id':managed.trade_plan_id if managed else None,
                'execution_id':managed.execution_id if managed else None,'manager_state':manager.state if manager else None,'automation_mode':manager.automation_mode if manager else None,
                'protection_state':manager.protection_state if manager else None,'active_exit_instructions':len(active),'audit':status,
            })
            if pid:seen_positions.add(pid)
    return {'generated_at':datetime.now(timezone.utc).isoformat(),'portfolio_id':portfolio_id,'broker_leg_count':len(rows),'managed_position_count':len(seen_positions),'pass_count':sum(1 for x in rows if x['audit']=='PASS_ARMED'),'fail_count':sum(1 for x in rows if x['audit']!='PASS_ARMED'),'rows':rows}


def main() -> None:
    parser=argparse.ArgumentParser(description='M74.6 recover platform BAG lineage from broker truth and audit autonomous exit arming')
    parser.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    parser.add_argument('--offline',action='store_true',help='Use latest persisted IBKR snapshot instead of reconnecting')
    args=parser.parse_args()
    sync=BrokerPortfolioSynchronizationService(SessionLocal).synchronize(args.portfolio_id,actor='M74_6_LINEAGE_RECOVERY',connect_broker=not args.offline)
    print(json.dumps({'sync':sync,'autonomous_exit_audit':audit(args.portfolio_id)},indent=2,sort_keys=True))


if __name__=='__main__':
    main()
