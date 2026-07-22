from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class ApiEnvelope(BaseModel):
    status: str = "ok"
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunRequest(BaseModel):
    requested_by: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=500)
    arguments: list[str] = Field(default_factory=list, max_length=50)


class WorkflowRunResult(BaseModel):
    workflow: str
    accepted: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    command: list[str] = Field(default_factory=list)
