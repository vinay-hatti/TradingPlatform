from __future__ import annotations
import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.inflection_intelligence.service import InstitutionalInflectionService

def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument('--limit',type=int); p.add_argument('--timeframe',default='1d'); p.add_argument('--build-mode',default='MANUAL',choices=['MANUAL','UNDERLYING_PRIMARY','OPTIONS_ENRICHMENT']); a=p.parse_args()
    print(json.dumps(InstitutionalInflectionService(SessionLocal).build(limit=a.limit,timeframe=a.timeframe,build_mode=a.build_mode),indent=2,sort_keys=True))
if __name__=='__main__': main()
