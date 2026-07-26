from __future__ import annotations
import argparse, json
from trading_ai.market_overview.service import MarketOverviewService

def main():
    parser=argparse.ArgumentParser(description='Build and persist the database-backed Market Overview snapshot')
    parser.add_argument('--universe',default='canonical')
    parser.add_argument('--no-persist',action='store_true')
    args=parser.parse_args()
    snapshot=MarketOverviewService().build(universe_name=args.universe,persist=not args.no_persist)
    print(json.dumps(snapshot.to_dict(),indent=2,default=str))
if __name__=='__main__': main()
