from __future__ import annotations
import json, tempfile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from trading_ai.trend_intelligence.operations_service import TrendOperationsService

def dump(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x))
def main():
 with tempfile.TemporaryDirectory() as td:
  r=Path(td); out=r/'reports/trend_intelligence'
  common={'status':'READY','snapshot_timestamp':'2026-07-28T22:00:00+00:00','symbols':[{'symbol':'AAPL','status':'READY','decision_adjustment':.05,'transition_state':'CONTINUATION'}]}
  for n in ['latest.json','transitions_latest.json','forecasts_latest.json','institutional_latest.json','platform_integration_latest.json']: dump(out/n,common)
  dump(r/'reports/market_ingestion/lifecycle_latest.json',{'status':'READY'})
  dump(r/'reports/published_state/current.json',{'status':'DEGRADED','usable':True})
  result=TrendOperationsService(r).run()
  assert result['status']=='READY',result
  assert result['milestone_52_closure_eligible'] is True
  for n in ['health','calibration','drift','attribution','governance','phase6']:
   assert (out/f'{n}_latest.json').exists()
  assert (out/'executive_summary_latest.html').exists()
 print('All Milestone 52 Phase 6 operational assertions passed.')
if __name__=='__main__': main()
