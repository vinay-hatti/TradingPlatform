from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

class RealtimeEvent(BaseModel):
    event_id: str
    event_type: str
    severity: Literal["INFO","WARNING","CRITICAL"] = "INFO"
    source: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)

class AlertRecord(BaseModel):
    alert_id: str
    rule_id: str
    severity: Literal["WARNING","CRITICAL"]
    title: str
    message: str
    source: str
    status: Literal["OPEN","ACKNOWLEDGED","RESOLVED"] = "OPEN"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None

class OperationalSnapshot(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_status: str
    connected_clients: int
    events_published: int
    open_alerts: int
    critical_alerts: int
    watched_artifacts: dict[str, dict[str, Any]]
