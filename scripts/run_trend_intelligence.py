import argparse,json
from pathlib import Path
from trading_ai.trend_intelligence import TrendIntelligenceService

def main():
 p=argparse.ArgumentParser(description='Build governed short/intermediate/long-term stock trend intelligence.')
 p.add_argument('--symbols',default='');p.add_argument('--no-persist',action='store_true');p.add_argument('--output',default='reports/trend_intelligence/latest.json');a=p.parse_args()
 symbols=[x.strip().upper() for x in a.symbols.split(',') if x.strip()] or None
 result=TrendIntelligenceService().build(symbols,persist=not a.no_persist)
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2,default=str))
 print(json.dumps({k:result.get(k) for k in ('status','snapshot_timestamp','requested_symbol_count','symbol_count','skipped_count','error_count')},indent=2));print(path)
if __name__=='__main__':main()
