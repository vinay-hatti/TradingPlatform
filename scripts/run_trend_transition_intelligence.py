import argparse,json
from pathlib import Path
from trading_ai.trend_intelligence.transition_service import TrendTransitionService
def main():
 p=argparse.ArgumentParser(); p.add_argument('--symbols',default=''); p.add_argument('--no-persist',action='store_true'); p.add_argument('--output',default='reports/trend_intelligence/transitions_latest.json'); a=p.parse_args()
 syms=[x.strip().upper() for x in a.symbols.split(',') if x.strip()] or None
 r=TrendTransitionService().build(syms,persist=not a.no_persist); path=Path(a.output); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(r,indent=2,default=str)); print(json.dumps({k:r[k] for k in ('status','snapshot_timestamp','requested_symbol_count','symbol_count','skipped_count','error_count')},indent=2)); print(path)
if __name__=='__main__':main()
