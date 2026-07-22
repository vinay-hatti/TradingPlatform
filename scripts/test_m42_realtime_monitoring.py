import asyncio, json, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from trading_ai.realtime_monitoring.service import RealtimeMonitoringService
async def main():
 with tempfile.TemporaryDirectory() as d:
  root=Path(d); (root/'m37').mkdir(); (root/'m37/execution_risk_control.json').write_text(json.dumps({'trading_control':'BLOCK_NEW_RISK','allow_new_risk':False}))
  svc=RealtimeMonitoringService(root); await svc.scan_once(); assert svc.bus.published>=2; assert svc.snapshot().critical_alerts==1; assert (root/'m42/alerts.json').exists()
asyncio.run(main()); print('Milestone 42 realtime monitoring assertions passed.')
