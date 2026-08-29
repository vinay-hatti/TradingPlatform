#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.setup_intelligence.service import SetupIntelligenceService


def parser():
    p=argparse.ArgumentParser(description="Milestone 78 governed institutional setup intelligence (shadow-only)")
    s=p.add_subparsers(dest="command",required=True)
    c=s.add_parser("capture"); c.add_argument("--symbols"); c.add_argument("--max-candidates",type=int)
    s.add_parser("materialize-outcomes")
    t=s.add_parser("train"); t.add_argument("--model-version")
    a=s.add_parser("approve-shadow"); a.add_argument("--model-id",required=True); a.add_argument("--actor",required=True); a.add_argument("--reason",required=True)
    a=s.add_parser("activate-shadow"); a.add_argument("--model-id",required=True); a.add_argument("--actor",required=True); a.add_argument("--reason",required=True)
    s.add_parser("predict")
    a=s.add_parser("certify-shadow"); a.add_argument("--setup-type",required=True); a.add_argument("--model-id",required=True); a.add_argument("--actor",required=True); a.add_argument("--reason",required=True)
    s.add_parser("status")
    return p


def main():
    args=parser().parse_args()
    with SessionLocal() as session:
        svc=SetupIntelligenceService(session)
        if args.command=="capture":
            symbols=[x.strip().upper() for x in (args.symbols or "").split(",") if x.strip()]
            out=svc.capture(symbols=symbols or None,max_candidates=args.max_candidates)
        elif args.command=="materialize-outcomes": out=svc.materialize_outcomes()
        elif args.command=="train": out=svc.train(model_version=args.model_version)
        elif args.command=="approve-shadow": out=svc.approve_shadow(args.model_id,actor=args.actor,reason=args.reason)
        elif args.command=="activate-shadow": out=svc.activate_shadow(args.model_id,actor=args.actor,reason=args.reason)
        elif args.command=="predict": out=svc.predict_latest()
        elif args.command=="certify-shadow": out=svc.certify(args.setup_type,args.model_id,actor=args.actor,reason=args.reason)
        else: out=svc.status()
    print(json.dumps(out,indent=2,sort_keys=True,default=str)); return 0

if __name__=="__main__": raise SystemExit(main())
