from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PromotionStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


class RuntimeStatus(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class BackupStatus(str, Enum):
    CREATED = "CREATED"
    VERIFIED = "VERIFIED"
    RESTORED = "RESTORED"
    FAILED = "FAILED"


class DeploymentPackage(BaseModel):
    package_id: str
    version: str
    environment: str
    archive_path: str
    manifest_path: str
    checksum_sha256: str
    created_at: datetime
    file_count: int
    size_bytes: int


class PromotionRecord(BaseModel):
    promotion_id: str
    package_id: str
    source_environment: str
    target_environment: str
    status: PromotionStatus
    requested_by: str
    reason: str
    requested_at: datetime
    completed_at: datetime | None = None
    validation_messages: list[str] = Field(default_factory=list)


class RuntimeComponent(BaseModel):
    name: str
    command: list[str] = Field(default_factory=list)
    pid: int | None = None
    status: RuntimeStatus = RuntimeStatus.UNKNOWN
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    restart_count: int = 0
    last_error: str | None = None
    log_path: str | None = None


class BackupRecord(BaseModel):
    backup_id: str
    archive_path: str
    checksum_sha256: str
    status: BackupStatus
    created_at: datetime
    verified_at: datetime | None = None
    restored_at: datetime | None = None
    included_paths: list[str] = Field(default_factory=list)
    size_bytes: int = 0


class DeploymentRecoverySummary(BaseModel):
    package_count: int
    promotion_count: int
    active_runtime_count: int
    backup_count: int
    verified_backup_count: int
    latest_package_version: str | None = None
    recovery_readiness: str


class DeploymentRecoveryState(BaseModel):
    generated_at: datetime
    summary: DeploymentRecoverySummary
    packages: list[DeploymentPackage] = Field(default_factory=list)
    promotions: list[PromotionRecord] = Field(default_factory=list)
    runtime_components: list[RuntimeComponent] = Field(default_factory=list)
    backups: list[BackupRecord] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class PackageCreateRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64)
    environment: str = Field(pattern="^(DEV|TEST|PAPER|STAGING|PRODUCTION)$")
    requested_by: str = Field(min_length=1, max_length=128)


class PromotionRequest(BaseModel):
    package_id: str
    source_environment: str
    target_environment: str
    requested_by: str
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)


class RuntimeActionRequest(BaseModel):
    actor: str
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)


class BackupCreateRequest(BaseModel):
    actor: str
    reason: str = Field(min_length=5, max_length=500)


class RestoreRequest(BaseModel):
    actor: str
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
