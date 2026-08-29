#!/usr/bin/env python
from __future__ import annotations
import argparse,json
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.publication_scope import latest_stock_scanner_run_id
from trading_ai.portfolio_risk_allocation.models import PortfolioIntelligencePublicationModel
from trading_ai.portfolio_risk_allocation.service import PortfolioRiskAllocationService
from trading_ai.portfolio_intelligence.models import ManagedPositionModel
from trading_ai.position_management.database_models import PositionExitInstructionModel

TERMINAL={'FILLED','CANCELLED','CANCELED','REJECTED','FAILED','SUPERSEDED','COMPLETED'}

def main():
    p=argparse.ArgumentParser(description='M64.2 governed trading-risk and expiration-exit audit')
    p.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    a=p.parse_args()
    svc=PortfolioRiskAllocationService(SessionLocal)
    latest_observed=svc.current(a.portfolio_id)
    with SessionLocal() as s:
        publication=s.scalar(select(PortfolioIntelligencePublicationModel).where(
            PortfolioIntelligencePublicationModel.portfolio_id==a.portfolio_id,
            PortfolioIntelligencePublicationModel.publication_name=='current_portfolio_allocation',
        ))
        authoritative_risk_id=publication.risk_snapshot_id if publication else None
        publication_payload=dict(publication.payload_json or {}) if publication else {}
        current_stock_run_id=latest_stock_scanner_run_id(s)
    snap=svc.snapshot(a.portfolio_id,authoritative_risk_id) if authoritative_risk_id else None
    if snap is None:
        raise RuntimeError(
            'No authoritative current_portfolio_allocation risk snapshot is available; '
            'run the M64.2.4 authoritative regeneration before auditing'
        )
    payload=dict(snap.get('payload_json') or {})
    capital=dict(payload.get('capital') or {})
    with SessionLocal() as s:
        positions=list(s.scalars(select(ManagedPositionModel).where(ManagedPositionModel.portfolio_id==a.portfolio_id,ManagedPositionModel.state.in_(['OPEN','PARTIAL','HEDGED','ROLLED']))))
        rows=[]
        for pos in positions:
            instructions=list(s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==pos.position_id)))
            guards=[x for x in instructions if str((x.payload or {}).get('label') or '')=='EXPIRATION_GUARD_EXIT' and str(x.status).upper() not in TERMINAL]
            guard=guards[-1] if guards else None
            gp=dict(guard.payload or {}) if guard else {}
            rows.append({'position_id':pos.position_id,'symbol':pos.symbol,'strategy':pos.strategy,'entry_value_premium_paid':pos.entry_value,'expiration_guard_status':guard.status if guard else 'MISSING','earliest_expiry':gp.get('earliest_expiry'),'mandatory_exit_on_or_before':gp.get('exit_on_or_before_date'),'execution_scope':gp.get('execution_scope'),'includes_short_legs':gp.get('includes_short_legs')})
    armed=sum(1 for row in rows if str(row['expiration_guard_status']).upper()=='ARMED')
    missing=sum(1 for row in rows if row['expiration_guard_status']=='MISSING')
    out={
        'version':'M64.2.4-RISK-EXPIRATION-AUDIT-1.0',
        'portfolio_id':a.portfolio_id,
        'decision_authority':{
            'status':'CURRENT' if publication_payload.get('stock_scanner_run_id')==current_stock_run_id else 'STALE',
            'publication_id':publication.publication_id,
            'published_at':publication.published_at,
            'stock_scanner_run_id':publication_payload.get('stock_scanner_run_id'),
            'current_stock_scanner_run_id':current_stock_run_id,
            'publication_matches_current_stock_run':publication_payload.get('stock_scanner_run_id')==current_stock_run_id,
            'authoritative_risk_snapshot_id':authoritative_risk_id,
            'latest_observed_risk_snapshot_id':None if latest_observed is None else latest_observed.get('snapshot_id'),
            'newer_unpublished_risk_observation_present':bool(latest_observed and latest_observed.get('snapshot_id')!=authoritative_risk_id),
        },
        'open_risk':capital.get('open_risk',snap.get('open_risk')),
        'gross_leg_open_risk':capital.get('gross_leg_open_risk'),
        'portfolio_heat_pct':capital.get('portfolio_heat_pct',snap.get('portfolio_heat_pct')),
        'trading_risk_basis':capital.get('trading_risk_basis'),
        'heat_risk_decomposition':capital.get('heat_risk_decomposition'),
        'operational_risk':capital.get('operational_risk'),
        'expiration_guard_summary':{'managed_positions':len(rows),'armed':armed,'missing':missing,'coverage_pct':round(armed/len(rows)*100,2) if rows else 100.0},
        'positions':rows,
    }
    print(json.dumps(out,indent=2,default=str))

if __name__=='__main__':main()
