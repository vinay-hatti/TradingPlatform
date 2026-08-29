from __future__ import annotations
import argparse, json
from trading_ai.broker_portfolio_sync.lineage_diagnostics import LineageDiagnosticsService
from trading_ai.database.session import SessionLocal

def main():
    p=argparse.ArgumentParser(description='M74.7 read-only execution/trade-plan/broker-position lineage diagnostics')
    p.add_argument('--portfolio-id',default='PAPER-PRIMARY')
    p.add_argument('--only-unmatched',action='store_true')
    a=p.parse_args()
    with SessionLocal() as s:
        out=LineageDiagnosticsService(s).diagnose(a.portfolio_id)
    if a.only_unmatched:
        out['positions']=[x for x in out['positions'] if x['recovery_classification']!='RECOVERED']
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=='__main__': main()
