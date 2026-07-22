from __future__ import annotations
import argparse, json, time
from pathlib import Path
from trading_ai.scanner.dashboard import DashboardConfiguration, ScannerDashboardService
from trading_ai.scanner.dashboard.progress_contracts import ProgressEventType, ScanProgressEvent
from trading_ai.scanner.dashboard.progress_serialization import read_events_jsonl
from trading_ai.scanner.dashboard.progress_service import LiveScanProgressService


def main() -> None:
    parser=argparse.ArgumentParser(description='M35 Phase 5 Step 2 live scan progress integration')
    parser.add_argument('--universe-name',default='US_ACTIVE_EQUITIES_ETFS'); parser.add_argument('--universe-size',type=int,required=True)
    parser.add_argument('--events-jsonl',type=Path); parser.add_argument('--output-dir',type=Path,default=Path('reports/m35/phase5/dashboard'))
    parser.add_argument('--checkpoint-every',type=int,default=100); parser.add_argument('--demo-events',type=int,default=0)
    args=parser.parse_args()
    dashboard=ScannerDashboardService(output_dir=args.output_dir)
    snapshot=dashboard.create_session(DashboardConfiguration())
    snapshot=dashboard.initialize(snapshot,universe_name=args.universe_name,universe_size=args.universe_size)
    snapshot=dashboard.start(snapshot)
    live=LiveScanProgressService(args.output_dir,checkpoint_every=args.checkpoint_every)
    events=read_events_jsonl(args.events_jsonl) if args.events_jsonl else []
    if args.demo_events:
        events=[ScanProgressEvent(ProgressEventType.SYMBOL_COMPLETED,symbol=f'DEMO{i:04d}',elapsed_seconds=max(1.0,i/20)) for i in range(1,args.demo_events+1)]
        events.append(ScanProgressEvent(ProgressEventType.SCAN_COMPLETED,elapsed_seconds=max(1.0,args.demo_events/20)))
    for event in events: snapshot=live.ingest(snapshot,event)
    health=live.health(snapshot)
    print(json.dumps({'session_id':snapshot.session.session_id,'status':snapshot.session.status.value,'completion_pct':snapshot.progress.completion_pct,'symbols_per_second':snapshot.progress.symbols_per_second,'healthy':health.healthy,'output_dir':str(args.output_dir)},indent=2))

if __name__=='__main__': main()
