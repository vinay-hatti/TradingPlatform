from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.scanner.dashboard import DashboardConfiguration,ScannerDashboardService
def main():
 with TemporaryDirectory() as d:
  out=Path(d); svc=ScannerDashboardService(output_dir=out); s=svc.create_session(DashboardConfiguration(top_n=25)); s=svc.initialize(s,universe_name='TEST',universe_size=25); s=svc.start(s); s=svc.update_progress(s,symbols_completed=25,elapsed_seconds=5); s=svc.complete(s); expected={'dashboard_state.json','scanner_session.json','navigation_state.json','ranking_snapshot.json','run.json','scanner_dashboard.html'}; assert expected.issubset({p.name for p in out.iterdir()})
 print('Milestone 35 Phase 5 Step 1 service assertions passed.')
if __name__=='__main__': main()
