from trading_ai.scanner.dashboard import DashboardConfiguration, ScannerDashboardEngine
from trading_ai.scanner.dashboard.progress_contracts import ProgressEventType, ScanProgressEvent
from trading_ai.scanner.dashboard.progress_engine import LiveScanProgressEngine

def main() -> None:
    base=ScannerDashboardEngine(); s=base.create_snapshot(DashboardConfiguration(autosave=False)); s=base.initialize_universe(s,universe_name='TEST',universe_size=100); s=base.start_scan(s)
    engine=LiveScanProgressEngine(); s=engine.apply(s,ScanProgressEvent(ProgressEventType.CHECKPOINT,completed_count=40,failed_count=2,skipped_count=3,elapsed_seconds=10))
    cp=engine.checkpoint(s,sequence=45,last_symbol='XYZ'); assert cp.completed_count==40 and cp.sequence==45 and s.progress.symbols_remaining==55
    print('Milestone 35 Phase 5 Step 2 resume assertions passed.')
if __name__=='__main__': main()
