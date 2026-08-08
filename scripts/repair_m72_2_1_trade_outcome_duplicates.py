#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from collections import defaultdict
from uuid import uuid4
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.performance_learning.models import TradeOutcomeModel, PerformanceObservationModel, LearningAuditEventModel
from trading_ai.performance_learning.service import now

VERSION='M72.2.1-EVIDENCE-INTEGRITY-HARDENING-1.0'
TERMINAL={'WIN','LOSS','FLAT'}

def _id(prefix): return f'{prefix}-{uuid4().hex.upper()}'

def analyze(session, portfolio_id):
    positions={x.position_id:x for x in session.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id==portfolio_id))}
    rows=list(session.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.portfolio_id==portfolio_id)))
    groups=defaultdict(list)
    for row in rows: groups[row.position_id].append(row)
    observations=list(session.scalars(select(PerformanceObservationModel).where(PerformanceObservationModel.portfolio_id==portfolio_id)))
    obs_keys={(x.position_id,int(x.position_version)) for x in observations}
    result=[]
    for position_id,items in sorted(groups.items()):
        if len(items)<=1: continue
        p=positions.get(position_id)
        terminal=[x for x in items if x.closed_at or x.outcome in TERMINAL]
        referenced=[x for x in items if (x.position_id,int(x.position_version)) in obs_keys]
        if terminal or referenced or p is None:
            status='MANUAL_REVIEW_REQUIRED'
        else:
            status='SAFE_SYNTHETIC_OPEN_DUPLICATES'
        canonical=next((x for x in items if p is not None and int(x.position_version)==int(p.version)),None)
        if canonical is None: canonical=max(items,key=lambda x:int(x.position_version))
        result.append({
            'position_id':position_id,'managed_version':None if p is None else int(p.version),'managed_state':None if p is None else p.state,
            'rows':len(items),'versions':sorted(int(x.position_version) for x in items),'canonical_outcome_id':canonical.outcome_id,
            'canonical_version':int(canonical.position_version),'remove_outcome_ids':[x.outcome_id for x in items if x.outcome_id!=canonical.outcome_id],
            'terminal_rows':len(terminal),'referenced_observations':len(referenced),'status':status,
        })
    return result,positions

def apply_repair(session, portfolio_id):
    analysis,positions=analyze(session,portfolio_id)
    consolidated=skipped=deleted=0
    for g in analysis:
        if g['status']!='SAFE_SYNTHETIC_OPEN_DUPLICATES': skipped+=1; continue
        items=list(session.scalars(select(TradeOutcomeModel).where(TradeOutcomeModel.position_id==g['position_id'])))
        canonical=next(x for x in items if x.outcome_id==g['canonical_outcome_id'])
        removed=[x for x in items if x.outcome_id!=canonical.outcome_id]
        p=positions[g['position_id']]
        audit_payload={
            'version':VERSION,'portfolio_id':portfolio_id,'position_id':g['position_id'],'managed_version':int(p.version),
            'kept':{'outcome_id':canonical.outcome_id,'position_version':int(canonical.position_version),'outcome':canonical.outcome,'reconstructed_at':canonical.reconstructed_at},
            'removed':[{'outcome_id':x.outcome_id,'position_version':int(x.position_version),'outcome':x.outcome,'reconstructed_at':x.reconstructed_at} for x in removed],
            'reason':'Consolidate synthetic OPEN trade-outcome rows created from operational managed-position version churn.',
        }
        session.add(LearningAuditEventModel(event_id=_id('M7221-AUDIT'),entity_id=g['position_id'],event_type='TRADE_OUTCOME_DUPLICATE_CONSOLIDATION',actor='m72.2.1-repair',reason=audit_payload['reason'],event_timestamp=now(),payload_json=audit_payload))
        for row in removed: session.delete(row); deleted+=1
        session.flush()
        canonical.position_version=int(p.version)
        canonical.payload_json={**(canonical.payload_json or {}),'m72_2_1_integrity':{'canonical_lifecycle_record':True,'consolidated_at':now(),'consolidated_versions':g['versions']}}
        canonical.reconstructed_at=now()
        consolidated+=1
    session.commit()
    return {'version':VERSION,'portfolio_id':portfolio_id,'groups':len(analysis),'consolidated':consolidated,'rows_deleted':deleted,'manual_review_required':skipped}

def main():
    ap=argparse.ArgumentParser(description='Governed M72.2.1 repair for synthetic OPEN trade-outcome duplicates.')
    ap.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    ap.add_argument('--apply',action='store_true',help='Apply only SAFE_SYNTHETIC_OPEN_DUPLICATES groups. Default is dry-run.')
    a=ap.parse_args()
    with SessionLocal() as s:
        analysis,_=analyze(s,a.portfolio_id)
        if not a.apply:
            print(json.dumps({'version':VERSION,'mode':'DRY_RUN','portfolio_id':a.portfolio_id,'duplicate_groups':analysis,'safe_groups':sum(1 for x in analysis if x['status']=='SAFE_SYNTHETIC_OPEN_DUPLICATES'),'manual_review_required':sum(1 for x in analysis if x['status']!='SAFE_SYNTHETIC_OPEN_DUPLICATES')},indent=2))
            return 0
        print(json.dumps(apply_repair(s,a.portfolio_id),indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
