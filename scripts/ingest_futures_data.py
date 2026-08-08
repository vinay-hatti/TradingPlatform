from __future__ import annotations
import argparse, os
from pathlib import Path
from datetime import date,timedelta
from trading_ai.database.session import SessionLocal
from trading_ai.futures_intelligence.service import FuturesIntelligenceService

def load_project_env():
    root=Path(__file__).resolve().parents[1]
    env_path=root/'.env'
    if not env_path.exists():
        return env_path
    for raw in env_path.read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key,value=line.split('=',1)
        key=key.strip();value=value.strip().strip('\"').strip("'")
        if key:
            os.environ.setdefault(key,value)
    return env_path

def main():
    env_path=load_project_env()
    p=argparse.ArgumentParser(description='Ingest ES/NQ/RTY futures data from Polygon/Massive Futures REST API')
    p.add_argument('--products',default='ES,NQ,RTY')
    p.add_argument('--start')
    p.add_argument('--end',default=date.today().isoformat())
    p.add_argument('--lookback-days',type=int,default=10)
    p.add_argument('--resolutions',default='1min,1session')
    p.add_argument('--min-days-to-maturity',type=int,default=5)
    a=p.parse_args();end=date.fromisoformat(a.end);start=a.start or (end-timedelta(days=a.lookback_days)).isoformat()
    if not (os.getenv('POLYGON_API_KEY') or os.getenv('MASSIVE_API_KEY')):
        raise RuntimeError(f'POLYGON_API_KEY (or MASSIVE_API_KEY) not found in environment or {env_path}')
    svc=FuturesIntelligenceService(SessionLocal)
    r=svc.ingest(tuple(x.strip().upper() for x in a.products.split(',') if x.strip()),start,a.end,tuple(x.strip() for x in a.resolutions.split(',') if x.strip()),a.min_days_to_maturity)
    import json;print(json.dumps(r,indent=2,default=str))
    return 0
if __name__=='__main__':raise SystemExit(main())
