from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

@dataclass(frozen=True)
class SourceEventRecord:
    calendar_source: str
    source_event_key: str
    symbol: str
    event_type: str
    event_date: date
    release_name: str
    event_time: time | None = None
    event_timezone: str = 'America/New_York'
    event_session: str | None = None
    event_time_status: str = 'UNKNOWN'
    date_status: str = 'CONFIRMED'
    event_components: tuple[str,...] = ()
    meeting_start_date: date | None = None
    meeting_end_date: date | None = None
    source_updated_at: str | None = None
    raw_payload: dict[str,Any] = field(default_factory=dict)
