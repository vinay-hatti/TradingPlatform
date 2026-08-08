from __future__ import annotations
import argparse, json
from uuid import uuid4
from sqlalchemy import select
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.models import OptionValuationEventModel

p=argparse.ArgumentParser(description='Manage governed Milestone 69 option-valuation events')
sub=p.add_subparsers(dest='command',required=True)
a=sub.add_parser('add');a.add_argument('--symbol',default='*');a.add_argument('--event-type',required=True);a.add_argument('--event-date',required=True);a.add_argument('--expected-move-pct',type=float);a.add_argument('--historical-move-pct',type=float);a.add_argument('--confidence',type=float,default=60);a.add_argument('--source',default='OPERATOR_GOVERNED')
l=sub.add_parser('list');l.add_argument('--status',default='ACTIVE')
d=sub.add_parser('disable');d.add_argument('--event-id',required=True)
args=p.parse_args()
with SessionLocal() as s:
    if args.command=='add':
        row=OptionValuationEventModel(event_id='M69-EVT-'+uuid4().hex.upper(),symbol=args.symbol.upper(),event_type=args.event_type.upper(),event_date=args.event_date,status='ACTIVE',expected_move_pct=args.expected_move_pct,historical_move_pct=args.historical_move_pct,confidence=args.confidence,source=args.source,payload_json={})
        s.add(row);s.commit();print(json.dumps({'event_id':row.event_id,'status':row.status},indent=2))
    elif args.command=='disable':
        row=s.get(OptionValuationEventModel,args.event_id)
        if not row:raise SystemExit('Event not found')
        row.status='DISABLED';s.commit();print(json.dumps({'event_id':row.event_id,'status':row.status},indent=2))
    else:
        rows=s.execute(select(OptionValuationEventModel).where(OptionValuationEventModel.status==args.status).order_by(OptionValuationEventModel.event_date)).scalars().all()
        print(json.dumps([{'event_id':r.event_id,'symbol':r.symbol,'event_type':r.event_type,'event_date':r.event_date,'expected_move_pct':r.expected_move_pct,'historical_move_pct':r.historical_move_pct,'confidence':r.confidence,'source':r.source,'status':r.status} for r in rows],indent=2))
