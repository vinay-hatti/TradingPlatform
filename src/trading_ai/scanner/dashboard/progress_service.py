from __future__ import annotations
from pathlib import Path
from .contracts import DashboardSnapshot
from .progress_contracts import ProgressHealth, ScanProgressEvent
from .progress_engine import LiveScanProgressEngine
from .progress_serialization import append_event_jsonl, write_checkpoint
from .reporting import write_dashboard_html
from .serialization import write_dashboard_artifacts


class LiveScanProgressService:
    def __init__(self, output_dir: Path | str = 'reports/m35/phase5/dashboard', engine: LiveScanProgressEngine | None = None, checkpoint_every: int = 100) -> None:
        self.output_dir=Path(output_dir); self.engine=engine or LiveScanProgressEngine(); self.checkpoint_every=max(1,checkpoint_every); self.sequence=0

    def ingest(self, snapshot: DashboardSnapshot, event: ScanProgressEvent) -> DashboardSnapshot:
        self.sequence += 1
        append_event_jsonl(self.output_dir/'progress_events.jsonl',event)
        snapshot=self.engine.apply(snapshot,event)
        write_dashboard_artifacts(self.output_dir,snapshot)
        write_dashboard_html(self.output_dir/'scanner_dashboard.html',snapshot)
        if self.sequence % self.checkpoint_every == 0 or event.event_type.value in {'CHECKPOINT','SCAN_COMPLETED'}:
            write_checkpoint(self.output_dir/'progress_checkpoint.json',self.engine.checkpoint(snapshot,sequence=self.sequence,last_symbol=event.symbol))
        return snapshot

    def health(self, snapshot: DashboardSnapshot, stale_after_seconds: float = 30.0) -> ProgressHealth:
        return self.engine.health(snapshot,stale_after_seconds=stale_after_seconds)
