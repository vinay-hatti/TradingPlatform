from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from trading_ai.trend_intelligence.operations_reporting import render_console
from trading_ai.trend_intelligence.operations_service import TrendOperationsService

def main():
 p=argparse.ArgumentParser(description='Run Milestone 52 Phase 6 monitoring, calibration, drift, attribution and governance.')
 p.add_argument('--root',default=str(ROOT)); p.add_argument('--json',action='store_true'); args=p.parse_args()
 result=TrendOperationsService(args.root).run(); print(json.dumps(result,indent=2,default=str) if args.json else render_console(result)); return 0 if result['status']!='FAILED' else 2
if __name__=='__main__': raise SystemExit(main())
