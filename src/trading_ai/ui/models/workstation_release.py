from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class WorkstationModuleStatus(BaseModel):
    name: str
    route: str
    api_path: str
    status: str
    available: bool
    detail: str = ""


class ReleaseReadinessCheck(BaseModel):
    name: str
    status: str
    required: bool = True
    detail: str = ""


class WorkstationReleaseSummary(BaseModel):
    milestone: str = "31"
    release_name: str = "Institutional Trading Workstation UI"
    release_version: str = "31.10.0"
    overall_status: str = "UNKNOWN"
    available_modules: int = 0
    unavailable_modules: int = 0
    passing_checks: int = 0
    warning_checks: int = 0
    failing_checks: int = 0


class WorkstationReleaseResponse(BaseModel):
    generated_at: datetime
    summary: WorkstationReleaseSummary
    modules: list[WorkstationModuleStatus] = Field(default_factory=list)
    readiness: list[ReleaseReadinessCheck] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
