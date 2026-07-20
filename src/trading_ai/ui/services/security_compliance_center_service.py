from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from trading_ai.ui.models.security_compliance_center import (
    AccessReviewRecord,
    ComplianceControl,
    EntitlementApprovalRequest,
    EntitlementChangeRecord,
    EntitlementChangeRequest,
    IdentityRecord,
    IdentityRequest,
    RoleRecord,
    RoleRequest,
    SecretMetadata,
    SecretMetadataRequest,
    SessionRecord,
    SessionRevokeRequest,
)


class SecurityComplianceCenterService:
    def __init__(
        self,
        state_path: str | Path = "reports/ui/security_compliance_state.json",
        audit_path: str | Path = "reports/audit/security_compliance_events.jsonl",
    ):
        self.state_path = Path(state_path)
        self.audit_path = Path(audit_path)
        self._lock = RLock()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _default_state(self):
        return {
            "identities": [],
            "roles": [],
            "entitlement_changes": [],
            "sessions": [],
            "secrets": [],
            "access_reviews": [],
        }

    def _load(self):
        if not self.state_path.exists():
            return self._default_state()
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        state = self._default_state()
        state.update(payload)
        return state

    def _save(self, state):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def _audit(self, event_type, actor, object_type, object_id, before, after):
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": self._now().isoformat(),
            "event_type": event_type,
            "actor_user_id": actor.user_id,
            "session_id": actor.session_id,
            "roles": actor.roles,
            "permissions": actor.permissions,
            "object_type": object_type,
            "object_id": object_id,
            "before": before,
            "after": after,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")

    @staticmethod
    def _require(actor, permission):
        if permission not in actor.permissions:
            raise PermissionError(f"Missing {permission} permission.")

    @staticmethod
    def _confirm(token):
        if not token.startswith("CONFIRM-SECURITY-"):
            raise PermissionError("Invalid security confirmation token.")

    def create_identity(self, request: IdentityRequest):
        self._require(request.actor, "security.identity.create")
        with self._lock:
            state = self._load()
            identity = IdentityRecord(
                identity_id=f"identity-{uuid4().hex[:16]}",
                display_name=request.display_name,
                email=request.email,
                identity_type=request.identity_type,
                status="ACTIVE",
                roles=request.roles,
                created_at=self._now(),
                updated_at=self._now(),
            )
            state["identities"].append(identity.model_dump(mode="json"))
            self._save(state)
            self._audit("IDENTITY_CREATED", request.actor, "identity",
                        identity.identity_id, None, identity.model_dump(mode="json"))
            return identity

    def list_identities(self):
        return [IdentityRecord.model_validate(v) for v in self._load()["identities"]]

    def create_role(self, request: RoleRequest):
        self._require(request.actor, "security.role.manage")
        with self._lock:
            state = self._load()
            if any(v["role_id"] == request.role_id for v in state["roles"]):
                raise ValueError("Role already exists.")
            role = RoleRecord(
                role_id=request.role_id,
                display_name=request.display_name,
                description=request.description,
                permissions=sorted(set(request.permissions)),
                privileged=request.privileged,
                created_at=self._now(),
                updated_at=self._now(),
            )
            state["roles"].append(role.model_dump(mode="json"))
            self._save(state)
            self._audit("ROLE_CREATED", request.actor, "role",
                        role.role_id, None, role.model_dump(mode="json"))
            return role

    def list_roles(self):
        return [RoleRecord.model_validate(v) for v in self._load()["roles"]]

    def request_entitlement_change(self, request: EntitlementChangeRequest):
        self._require(request.actor, "security.entitlement.request")
        self._confirm(request.confirmation_token)
        if not any(i.identity_id == request.identity_id for i in self.list_identities()):
            raise KeyError(request.identity_id)
        known_roles = {r.role_id for r in self.list_roles()}
        unknown = (set(request.add_roles) | set(request.remove_roles)) - known_roles
        if unknown:
            raise ValueError(f"Unknown roles: {sorted(unknown)}")
        with self._lock:
            state = self._load()
            record = EntitlementChangeRecord(
                change_id=f"entitlement-{uuid4().hex[:16]}",
                identity_id=request.identity_id,
                requested_at=self._now(),
                requested_by=request.actor.user_id,
                add_roles=request.add_roles,
                remove_roles=request.remove_roles,
                reason=request.reason,
                status="REQUESTED",
            )
            state["entitlement_changes"].append(record.model_dump(mode="json"))
            self._save(state)
            self._audit("ENTITLEMENT_CHANGE_REQUESTED", request.actor, "entitlement_change",
                        record.change_id, None, record.model_dump(mode="json"))
            return record

    def approve_entitlement_change(self, change_id: str, request: EntitlementApprovalRequest):
        self._require(request.actor, "security.entitlement.approve")
        self._confirm(request.confirmation_token)
        with self._lock:
            state = self._load()
            index = next((i for i, v in enumerate(state["entitlement_changes"])
                          if v["change_id"] == change_id), None)
            if index is None:
                raise KeyError(change_id)
            record = EntitlementChangeRecord.model_validate(state["entitlement_changes"][index])
            if record.requested_by == request.actor.user_id:
                raise PermissionError("Four-eye approval requires a different user.")
            before = record.model_dump(mode="json")
            if request.decision == "REJECT":
                record.status = "REJECTED"
            else:
                record.status = "APPROVED"
                record.approved_by = request.actor.user_id
                record.approved_at = self._now()
            state["entitlement_changes"][index] = record.model_dump(mode="json")
            self._save(state)
            self._audit("ENTITLEMENT_CHANGE_APPROVED", request.actor, "entitlement_change",
                        change_id, before, record.model_dump(mode="json"))
            return record

    def apply_entitlement_change(self, change_id: str, actor):
        self._require(actor, "security.entitlement.apply")
        with self._lock:
            state = self._load()
            ci = next((i for i, v in enumerate(state["entitlement_changes"])
                       if v["change_id"] == change_id), None)
            if ci is None:
                raise KeyError(change_id)
            change = EntitlementChangeRecord.model_validate(state["entitlement_changes"][ci])
            if change.status != "APPROVED":
                raise ValueError("Entitlement change must be approved before application.")
            ii = next((i for i, v in enumerate(state["identities"])
                       if v["identity_id"] == change.identity_id), None)
            if ii is None:
                raise KeyError(change.identity_id)
            identity = IdentityRecord.model_validate(state["identities"][ii])
            before = identity.model_dump(mode="json")
            roles = set(identity.roles)
            roles.update(change.add_roles)
            roles.difference_update(change.remove_roles)
            identity.roles = sorted(roles)
            identity.updated_at = self._now()
            change.status = "APPLIED"
            change.applied_at = self._now()
            state["identities"][ii] = identity.model_dump(mode="json")
            state["entitlement_changes"][ci] = change.model_dump(mode="json")
            self._save(state)
            self._audit("ENTITLEMENT_CHANGE_APPLIED", actor, "identity",
                        identity.identity_id, before, identity.model_dump(mode="json"))
            return change

    def list_entitlement_changes(self):
        return [EntitlementChangeRecord.model_validate(v)
                for v in self._load()["entitlement_changes"]]

    def list_sessions(self):
        now = self._now()
        output = []
        for raw in self._load()["sessions"]:
            session = SessionRecord.model_validate(raw)
            if session.status == "ACTIVE" and session.expires_at <= now:
                session.status = "EXPIRED"
            output.append(session)
        return output

    def revoke_session(self, session_id: str, request: SessionRevokeRequest):
        self._require(request.actor, "security.session.revoke")
        self._confirm(request.confirmation_token)
        with self._lock:
            state = self._load()
            index = next((i for i, v in enumerate(state["sessions"])
                          if v["session_id"] == session_id), None)
            if index is None:
                raise KeyError(session_id)
            session = SessionRecord.model_validate(state["sessions"][index])
            before = session.model_dump(mode="json")
            session.status = "REVOKED"
            session.revoked_by = request.actor.user_id
            session.revoked_at = self._now()
            session.revoke_reason = request.reason
            state["sessions"][index] = session.model_dump(mode="json")
            self._save(state)
            self._audit("SESSION_REVOKED", request.actor, "session",
                        session_id, before, session.model_dump(mode="json"))
            return session

    def register_secret_metadata(self, request: SecretMetadataRequest):
        self._require(request.actor, "security.secret.metadata")
        with self._lock:
            state = self._load()
            now = self._now()
            if request.expires_at is None:
                status = "UNKNOWN"
            elif request.expires_at <= now:
                status = "OVERDUE"
            elif request.expires_at <= now + timedelta(days=30):
                status = "DUE_SOON"
            else:
                status = "CURRENT"
            secret = SecretMetadata(
                secret_id=request.secret_id,
                display_name=request.display_name,
                provider=request.provider,
                environment=request.environment,
                reference=request.reference,
                last_rotated_at=request.last_rotated_at,
                expires_at=request.expires_at,
                rotation_status=status,
                value_visible=False,
            )
            existing = next((i for i, v in enumerate(state["secrets"])
                             if v["secret_id"] == request.secret_id), None)
            if existing is None:
                state["secrets"].append(secret.model_dump(mode="json"))
            else:
                state["secrets"][existing] = secret.model_dump(mode="json")
            self._save(state)
            self._audit("SECRET_METADATA_REGISTERED", request.actor, "secret_metadata",
                        secret.secret_id, None, secret.model_dump(mode="json"))
            return secret

    def list_secret_metadata(self):
        return [SecretMetadata.model_validate(v) for v in self._load()["secrets"]]

    def create_access_review(self, actor):
        self._require(actor, "security.access_review.create")
        identities = self.list_identities()
        privileged_roles = {r.role_id for r in self.list_roles() if r.privileged}
        privileged = [i for i in identities if set(i.roles) & privileged_roles]
        findings = []
        for identity in identities:
            if identity.status == "ACTIVE" and not identity.roles:
                findings.append(f"{identity.identity_id} has no assigned roles.")
        for identity in privileged:
            if identity.last_reviewed_at is None:
                findings.append(f"{identity.identity_id} has privileged access without a prior review.")
        record = AccessReviewRecord(
            review_id=f"review-{uuid4().hex[:16]}",
            created_at=self._now(),
            created_by=actor.user_id,
            status="OPEN",
            identity_count=len(identities),
            privileged_identity_count=len(privileged),
            findings=findings,
        )
        with self._lock:
            state = self._load()
            state["access_reviews"].append(record.model_dump(mode="json"))
            self._save(state)
        self._audit("ACCESS_REVIEW_CREATED", actor, "access_review",
                    record.review_id, None, record.model_dump(mode="json"))
        return record

    def compliance_controls(self):
        identities = self.list_identities()
        roles = self.list_roles()
        secrets = self.list_secret_metadata()
        active_sessions = [s for s in self.list_sessions() if s.status == "ACTIVE"]
        privileged_roles = [r for r in roles if r.privileged]
        controls = [
            ComplianceControl(
                control_id="IAM-001", framework="INTERNAL",
                title="Identity inventory maintained",
                description="Human and service identities are inventoried.",
                status="PASS" if identities else "NOT_ASSESSED",
                evidence=[f"{len(identities)} identities recorded."],
                assessed_at=self._now(),
            ),
            ComplianceControl(
                control_id="IAM-002", framework="INTERNAL",
                title="Privileged roles identified",
                description="Privileged roles are explicitly marked.",
                status="PASS" if privileged_roles else "PARTIAL",
                evidence=[f"{len(privileged_roles)} privileged roles recorded."],
                assessed_at=self._now(),
            ),
            ComplianceControl(
                control_id="SEC-001", framework="INTERNAL",
                title="Secret values are not exposed",
                description="The UI stores and displays secret metadata only.",
                status="PASS",
                evidence=[f"{len(secrets)} secret metadata records; value_visible is always false."],
                assessed_at=self._now(),
            ),
            ComplianceControl(
                control_id="SES-001", framework="INTERNAL",
                title="Active sessions are visible and revocable",
                description="Security administrators can review and revoke sessions.",
                status="PASS",
                evidence=[f"{len(active_sessions)} active sessions recorded."],
                assessed_at=self._now(),
            ),
        ]
        return controls
