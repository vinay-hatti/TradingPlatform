#!/usr/bin/env python
from __future__ import annotations
import argparse,json
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.broker_portfolio_sync.service import BrokerPortfolioSynchronizationService
from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.autonomous_position_management.models import M73PositionManagerModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TERMINAL={'FILLED','CANCELLED','CANCELED','REJECTED','FAILED','SUPERSEDED','COMPLETED'}

def main():
    ap=argparse.ArgumentParser(description='M74.13 reconcile platform ownership and autonomous exit bootstrap')
    ap.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    ap.add_argument('--offline',action='store_true',help='Use latest persisted broker snapshot without connecting TWS')
    a=ap.parse_args()
    sync=BrokerPortfolioSynchronizationService(SessionLocal).synchronize(a.portfolio_id,actor='M74_13_OWNERSHIP_RECONCILE',connect_broker=not a.offline)
    rows=[]
    with SessionLocal() as s:
        broker=list(s.scalars(select(BrokerCurrentPositionModel).where(BrokerCurrentPositionModel.portfolio_id==a.portfolio_id,BrokerCurrentPositionModel.active.is_(True),BrokerCurrentPositionModel.signed_quantity!=0)).all())
        seen=set()
        for bp in broker:
            pid=bp.managed_position_id
            if not pid or pid in seen:continue
            seen.add(pid)
            p=s.get(ManagedPositionModel,pid)
            if not p:continue
            mgr=s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id==pid))
            exits=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==pid)).all())
            active=[x for x in exits if str(x.status or '').upper() not in TERMINAL]
            meta=dict(p.metadata_json or {});own=dict(meta.get('position_ownership') or {})
            auto=bool(own.get('origin')=='PLATFORM' and str(meta.get('automation_mode') or '').upper()=='FULLY_AUTOMATIC' and mgr and str(mgr.state or '').upper()=='ACTIVE' and active)
            rows.append({'symbol':p.symbol,'strategy':p.strategy,'position_id':p.position_id,'trade_plan_id':p.trade_plan_id,'execution_id':p.execution_id,'ownership_origin':own.get('origin') or ('PLATFORM' if p.execution_id else 'UNVERIFIED'),'ownership_authority':own.get('authority'),'bootstrap_state':own.get('bootstrap_state') or meta.get('m74_13_bootstrap_state'),'automation_mode':meta.get('automation_mode'),'manager_state':mgr.state if mgr else None,'protection_state':mgr.protection_state if mgr else None,'active_exit_instructions':len(active),'status':'AUTO_MANAGED' if auto else ('AUTO_BOOTSTRAPPING' if own.get('origin')=='PLATFORM' else 'MANUAL_REQUIRED')})
    summary={'AUTO_MANAGED':sum(x['status']=='AUTO_MANAGED' for x in rows),'AUTO_BOOTSTRAPPING':sum(x['status']=='AUTO_BOOTSTRAPPING' for x in rows),'MANUAL_REQUIRED':sum(x['status']=='MANUAL_REQUIRED' for x in rows)}
    print(json.dumps({'version':'M74.13-AUTONOMOUS-POSITION-OWNERSHIP-1.0','portfolio_id':a.portfolio_id,'sync':sync,'summary':summary,'positions':sorted(rows,key=lambda x:(x['status'],x['symbol']))},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
