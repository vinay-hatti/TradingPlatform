from __future__ import annotations
import argparse,json
from pathlib import Path
from trading_ai.database import SessionLocal
from trading_ai.historical_underlying_replay.analytics import HistoricalChampionAnalyticsService
def main():
 p=argparse.ArgumentParser(description='M77.1.1 read-only historical champion analytics'); p.add_argument('--replay-run-id'); p.add_argument('--output'); a=p.parse_args()
 with SessionLocal() as s: report=HistoricalChampionAnalyticsService(s).build_report(a.replay_run_id)
 rendered=json.dumps(report,default=str,indent=2); print('=== M77.1.1 HISTORICAL CHAMPION ANALYTICS ==='); print(rendered)
 if a.output: Path(a.output).write_text(rendered+'\n')
 return 0
if __name__=='__main__': raise SystemExit(main())
