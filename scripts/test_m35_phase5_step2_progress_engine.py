from datetime import timedelta
from trading_ai.scanner.dashboard import DashboardConfiguration, ScannerDashboardEngine
from trading_ai.scanner.dashboard.progress_contracts import ProgressEventType, ScanProgressEvent
from trading_ai.scanner.dashboard.progress_engine import LiveScanProgressEngine, utc_now


def main() -> None:
    base=ScannerDashboardEngine(); s=base.create_snapshot(DashboardConfiguration(autosave=False)); s=base.initialize_universe(s,universe_name='TEST',universe_size=10); s=base.start_scan(s)
    engine=LiveScanProgressEngine()
    s=engine.apply(s,ScanProgressEvent(ProgressEventType.SYMBOL_COMPLETED,symbol='AAPL',elapsed_seconds=2.0))
    s=engine.apply(s,ScanProgressEvent(ProgressEventType.SYMBOL_FAILED,symbol='BAD',elapsed_seconds=4.0))
    assert s.progress.symbols_completed==1 and s.progress.symbols_failed==1
    assert s.progress.symbols_remaining==8 and s.progress.symbols_per_second==0.5
    health=engine.health(s,stale_after_seconds=30,now=s.session.last_refresh_at+timedelta(seconds=31))
    assert health.stale and not health.healthy
    print('Milestone 35 Phase 5 Step 2 progress engine assertions passed.')
if __name__=='__main__': main()
