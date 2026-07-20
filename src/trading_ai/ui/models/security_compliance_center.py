from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from trading_ai.ui.models.paper_commands import GovernedActor


class IdentityRecord(BaseModel):
    identity_id: str
    display_name: str
    email: str | None = None
    identity_type: Literal["HUMAN", "SERVICE"]
    status: Literal["ACTIVE", "SUSPENDED", "DISABLED"]
    roles: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    last_reviewed_at: datetime | None = None


class IdentityRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    identity_type: Literal["HUMAN", "SERVICE"] = "HUMAN"
    roles: list[str] = Field(default_factory=list, max_length=30)
    actor: GovernedActor


class RoleRecord(BaseModel):
    role_id: str
    display_name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)
    privileged: bool = False
    created_at: datetime
    updated_at: datetime


class RoleRequest(BaseModel):
    role_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    permissions: list[str] = Field(default_factory=list, max_length=200)
    privileged: bool = False
    actor: GovernedActor


class EntitlementChangeRequest(BaseModel):
    identity_id: str
    add_roles: list[str] = Field(default_factory=list)
    remove_roles: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    actor: GovernedActor

    @model_validator(mode="after")
    def changes_required(self):
        if not self.add_roles and not self.remove_roles:
            raise ValueError("At least one role change is required.")
        overlap = set(self.add_roles) & set(self.remove_roles)
        if overlap:
            raise ValueError(f"Roles cannot be both added and removed: {sorted(overlap)}")
        return self


class EntitlementChangeRecord(BaseModel):
    change_id: str
    identity_id: str
    requested_at: datetime
    requested_by: str
    add_roles: list[str]
    remove_roles: list[str]
    reason: str
    status: Literal["REQUESTED", "APPROVED", "REJECTED", "APPLIED"]
    approved_by: str | None = None
    approved_at: datetime | None = None
    applied_at: datetime | None = None


class EntitlementApprovalRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    actor: GovernedActor


class SessionRecord(BaseModel):
    session_id: str
    identity_id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    status: Literal["ACTIVE", "REVOKED", "EXPIRED"]
    client_label: str = "unknown"
    ip_masked: str = "unknown"
    revoked_by: str | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


class SessionRevokeRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    confirmation_token: str = Field(min_length=8, max_length=256)
    actor: GovernedActor


class SecretMetadata(BaseModel):
    secret_id: str
    display_name: str
    provider: str
    environment: str
    reference: str
    last_rotated_at: datetime | None = None
    expires_at: datetime | None = None
    rotation_status: Literal["CURRENT", "DUE_SOON", "OVERDUE", "UNKNOWN"] = "UNKNOWN"
    value_visible: Literal[False] = False


class SecretMetadataRequest(BaseModel):
    secret_id: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=160)
    provider: str = Field(min_length=1, max_length=120)
    environment: str = Field(min_length=1, max_length=80)
    reference: str = Field(min_length=1, max_length=500)
    last_rotated_at: datetime | None = None
    expires_at: datetime | None = None
    actor: GovernedActor


class ComplianceControl(BaseModel):
    control_id: str
    framework: str
    title: str
    description: str
    status: Literal["PASS", "FAIL", "PARTIAL", "NOT_ASSESSED"]
    evidence: list[str] = Field(default_factory=list)
    owner: str | None = None
    assessed_at: datetime | None = None


class AccessReviewRecord(BaseModel):
    review_id: str
    created_at: datetime
    created_by: str
    status: Literal["OPEN", "COMPLETE"]
    identity_count: int
    privileged_identity_count: int
    findings: list[str] = Field(default_factory=list)
