#!/usr/bin/env python
from __future__ import annotations
import argparse,json,os,time
from pathlib import Path
from trading_ai.database.session import SessionLocal
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager
from trading_ai.execution_intelligence.policy import load_execution_intelligence_policy
from trading_ai.autonomous_position_management import AutonomousPositionManagementService, load_m73_policy
from trading_ai.lifecycle_governance import LifecycleGovernanceService

RUNTIME=Path('.runtime')
POSITION_MARKER=RUNTIME/'m74_13_position_management_last_run'
M75_AUDIT_MARKER=RUNTIME/'m75_lifecycle_audit_last_run'

def _position_management_due() -> bool:
    interval=max(10.0,float(os.getenv('TRADING_AI_M74_13_POSITION_MANAGEMENT_INTERVAL_SECONDS','30')))
    try:
        last=float(POSITION_MARKER.read_text().strip())
    except Exception:
        return True
    return time.time()-last>=interval

def _run_position_management(portfolio_id):
    policy=load_m73_policy()
    if not policy.enabled:return {'status':'DISABLED'}
    if not _position_management_due():return {'status':'NOT_DUE'}
    RUNTIME.mkdir(parents=True,exist_ok=True)
    try:
        with SessionLocal() as s:
            result=AutonomousPositionManagementService(s).run_cycle(portfolio_id=portfolio_id,actor='M74_13_CANONICAL_EXECUTION_MANAGER',submit_automatic=True,limit=250)
        POSITION_MARKER.write_text(str(time.time()))
        return result
    except Exception as exc:
        return {'status':'DEGRADED','error':f'{type(exc).__name__}: {exc}'}



def _m75_audit_due() -> bool:
    interval=max(3600.0,float(os.getenv('TRADING_AI_M75_LIFECYCLE_AUDIT_INTERVAL_SECONDS','86400')))
    try:
        last=float(M75_AUDIT_MARKER.read_text().strip())
    except Exception:
        return True
    return time.time()-last>=interval

def _run_lifecycle_governance(portfolio_id):
    try:
        RUNTIME.mkdir(parents=True,exist_ok=True)
        with SessionLocal() as s:
            svc=LifecycleGovernanceService(s)
            finalization=svc.reconcile_terminal_positions(portfolio_id=portfolio_id,actor='M75_CANONICAL_EXECUTION_MANAGER',commit=True)
            audit=None
            if _m75_audit_due():
                audit=svc.audit(portfolio_id=portfolio_id)
                M75_AUDIT_MARKER.write_text(str(time.time()))
        return {'status':'READY' if not audit or audit.get('status')=='CERTIFIED' else 'DEGRADED','finalization':finalization,'audit':audit}
    except Exception as exc:
        return {'status':'DEGRADED','error':f'{type(exc).__name__}: {exc}'}

def once(portfolio_id):
    with SessionLocal() as s:
        result=AutomaticEntryFillManager(s).cycle(portfolio_id)
    # Reuse the same canonical LaunchAgent for post-fill position management and M75 lifecycle governance.
    result['lifecycle_governance']=_run_lifecycle_governance(portfolio_id)
    result['autonomous_position_management']=_run_position_management(portfolio_id)
    return result

def main():
    ap=argparse.ArgumentParser(description="M73/M74 canonical automatic entry-fill and autonomous position manager")
    ap.add_argument("--portfolio-id",default="PAPER-PRIMARY")
    ap.add_argument("--daemon",action="store_true")
    ap.add_argument("--interval-seconds",type=float,default=None)
    a=ap.parse_args();policy=load_execution_intelligence_policy();interval=max(1.0,a.interval_seconds or policy.automatic_fill_interval_seconds)
    while True:
        print(json.dumps(once(a.portfolio_id),indent=2),flush=True)
        if not a.daemon:return 0
        time.sleep(interval)
if __name__=="__main__":raise SystemExit(main())
