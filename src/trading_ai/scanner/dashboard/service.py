from pathlib import Path
from typing import Iterable
from .contracts import DashboardConfiguration,DashboardSnapshot,DashboardView,RankingRecord
from .engine import ScannerDashboardEngine
from .reporting import write_dashboard_html
from .serialization import write_dashboard_artifacts
class ScannerDashboardService:
    def __init__(self,engine=None,output_dir:Path|str='reports/m35/phase5/dashboard'): self.engine=engine or ScannerDashboardEngine(); self.output_dir=Path(output_dir)
    def create_session(self,configuration:DashboardConfiguration|None=None): return self._persist(self.engine.create_snapshot(configuration))
    def initialize(self,snapshot,*,universe_name,universe_size): return self._persist(self.engine.initialize_universe(snapshot,universe_name=universe_name,universe_size=universe_size))
    def start(self,snapshot): return self._persist(self.engine.start_scan(snapshot))
    def pause(self,snapshot): return self._persist(self.engine.pause_scan(snapshot))
    def update_progress(self,snapshot,**kwargs): return self._persist(self.engine.update_progress(snapshot,**kwargs))
    def update_rankings(self,snapshot,rankings:Iterable[RankingRecord]): return self._persist(self.engine.update_rankings(snapshot,rankings))
    def navigate(self,snapshot,view:DashboardView,selected_symbol=None): return self._persist(self.engine.navigate(snapshot,view,selected_symbol))
    def complete(self,snapshot): return self._persist(self.engine.complete_scan(snapshot))
    def fail(self,snapshot,reason): return self._persist(self.engine.fail_scan(snapshot,reason))
    def _persist(self,snapshot):
        if snapshot.configuration.autosave: write_dashboard_artifacts(self.output_dir,snapshot); write_dashboard_html(self.output_dir/'scanner_dashboard.html',snapshot)
        return snapshot
