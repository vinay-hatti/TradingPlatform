from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.dashboard import DashboardConfiguration, ScannerDashboardEngine
from trading_ai.scanner.dashboard.progress_contracts import ProgressEventType, ScanProgressEvent
from trading_ai.scanner.dashboard.progress_service import LiveScanProgressService


def main() -> None:
    with TemporaryDirectory() as d:
        base=ScannerDashboardEngine(); s=base.create_snapshot(DashboardConfiguration(autosave=False)); s=base.initialize_universe(s,universe_name='TEST',universe_size=2); s=base.start_scan(s)
        service=LiveScanProgressService(d,checkpoint_every=1)
        s=service.ingest(s,ScanProgressEvent(ProgressEventType.SYMBOL_COMPLETED,symbol='AAPL',elapsed_seconds=1.0))
        assert (Path(d)/'progress_events.jsonl').exists(); assert (Path(d)/'progress_checkpoint.json').exists(); assert (Path(d)/'dashboard_state.json').exists()
        print('Milestone 35 Phase 5 Step 2 progress service assertions passed.')
if __name__=='__main__': main()
