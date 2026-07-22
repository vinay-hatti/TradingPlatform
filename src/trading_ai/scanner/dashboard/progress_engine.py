from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from .contracts import DashboardEvent, DashboardEventType, DashboardSnapshot, ScannerProgress, ScannerStatus
from .progress_contracts import ProgressCheckpoint, ProgressEventType, ProgressHealth, ScanProgressEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LiveScanProgressEngine:
    def apply(self, snapshot: DashboardSnapshot, event: ScanProgressEvent) -> DashboardSnapshot:
        p = snapshot.progress
        completed, failed, skipped = p.symbols_completed, p.symbols_failed, p.symbols_skipped
        if event.completed_count is not None:
            completed = max(0, event.completed_count)
        elif event.event_type is ProgressEventType.SYMBOL_COMPLETED:
            completed += 1
        if event.failed_count is not None:
            failed = max(0, event.failed_count)
        elif event.event_type is ProgressEventType.SYMBOL_FAILED:
            failed += 1
        if event.skipped_count is not None:
            skipped = max(0, event.skipped_count)
        elif event.event_type is ProgressEventType.SYMBOL_SKIPPED:
            skipped += 1
        elapsed = max(p.elapsed_seconds, float(event.elapsed_seconds or 0.0))
        processed = completed + failed + skipped
        rate = processed / elapsed if elapsed > 0 else p.symbols_per_second
        remaining = max(0, p.universe_size - processed)
        eta = remaining / rate if rate > 0 else None
        progress = ScannerProgress(p.universe_size, completed, failed, skipped, rate, elapsed, eta)
        dashboard_event = DashboardEvent(
            DashboardEventType.SCAN_COMPLETED if event.event_type is ProgressEventType.SCAN_COMPLETED else DashboardEventType.PROGRESS_UPDATED,
            occurred_at=event.occurred_at,
            payload={"progress_event_type": event.event_type.value, "symbol": event.symbol, "processed": processed, "message": event.message},
        )
        status = ScannerStatus.COMPLETED if event.event_type is ProgressEventType.SCAN_COMPLETED else snapshot.session.status
        session = replace(snapshot.session, status=status, completed_at=event.occurred_at if status is ScannerStatus.COMPLETED else snapshot.session.completed_at, last_refresh_at=event.occurred_at)
        events = tuple(snapshot.events) + (dashboard_event,) if snapshot.configuration.persist_events else (dashboard_event,)
        return replace(snapshot, generated_at=event.occurred_at, progress=progress, session=session, events=events)

    def checkpoint(self, snapshot: DashboardSnapshot, *, sequence: int, last_symbol: str | None = None) -> ProgressCheckpoint:
        return ProgressCheckpoint(
            session_id=snapshot.session.session_id,
            universe_size=snapshot.progress.universe_size,
            completed_count=snapshot.progress.symbols_completed,
            failed_count=snapshot.progress.symbols_failed,
            skipped_count=snapshot.progress.symbols_skipped,
            elapsed_seconds=snapshot.progress.elapsed_seconds,
            last_symbol=last_symbol,
            last_event_at=snapshot.session.last_refresh_at,
            sequence=sequence,
        )

    def health(self, snapshot: DashboardSnapshot, *, stale_after_seconds: float, now: datetime | None = None) -> ProgressHealth:
        now = now or utc_now()
        age = max(0.0, (now - snapshot.session.last_refresh_at).total_seconds())
        stale = snapshot.session.status is ScannerStatus.SCANNING and age > stale_after_seconds
        return ProgressHealth(not stale, stale, age, "no progress heartbeat within threshold" if stale else None)
