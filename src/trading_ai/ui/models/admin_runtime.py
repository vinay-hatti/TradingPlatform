from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class EnvironmentProfile(BaseModel):
    environment: str = "UNKNOWN"
    profile_name: str = "UNKNOWN"
    version: str | None = None
    active: bool = False
    source: str = ""
    modified_at: datetime | None = None

class RuntimeComponent(BaseModel):
    name: str
    status: str = "UNKNOWN"
    detail: str = ""
    last_checked_at: datetime | None = None
    latency_ms: float | None = None
    source: str = ""

class FeatureFlag(BaseModel):
    name: str
    enabled: bool
    scope: str = "runtime"
    description: str = ""
    source: str = ""

class ReadinessCheck(BaseModel):
    name: str
    status: str
    detail: str = ""
    required: bool = True

class ConfigurationDrift(BaseModel):
    key: str
    expected: str | None = None
    actual: str | None = None
    status: str = "UNKNOWN"
    source: str = ""

class RuntimeSummary(BaseModel):
    environment: str = "UNKNOWN"
    profile_name: str = "UNKNOWN"
    readiness_status: str = "UNKNOWN"
    healthy_components: int = 0
    degraded_components: int = 0
    failed_components: int = 0
    enabled_feature_flags: int = 0
    disabled_feature_flags: int = 0
    configuration_drift_count: int = 0
    control_mode: str = "READ_ONLY"

class AdminRuntimeResponse(BaseModel):
    generated_at: datetime
    available: bool
    stale: bool
    age_seconds: float | None = None
    source_detail: str
    summary: RuntimeSummary
    profiles: list[EnvironmentProfile] = Field(default_factory=list)
    components: list[RuntimeComponent] = Field(default_factory=list)
    feature_flags: list[FeatureFlag] = Field(default_factory=list)
    readiness: list[ReadinessCheck] = Field(default_factory=list)
    drift: list[ConfigurationDrift] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)

class RuntimeControlRequest(BaseModel):
    reason: str = "Requested from institutional workstation"

class RuntimeControlResult(BaseModel):
    accepted: bool
    action: str
    target: str
    message: str
    requested_at: datetime
