from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.ui.models.paper_commands import GovernedActor
from trading_ai.ui.models.security_compliance_center import (
    EntitlementApprovalRequest,
    EntitlementChangeRequest,
    IdentityRequest,
    RoleRequest,
    SecretMetadataRequest,
)
from trading_ai.ui.services.security_compliance_center_service import (
    SecurityComplianceCenterService,
)

def main():
    requester=GovernedActor(
        user_id="security-requester",session_id="s1",roles=["SECURITY_ADMIN"],
        permissions=[
            "security.identity.create","security.role.manage",
            "security.entitlement.request","security.secret.metadata",
            "security.access_review.create",
        ])
    approver=GovernedActor(
        user_id="security-approver",session_id="s2",roles=["SECURITY_APPROVER"],
        permissions=["security.entitlement.approve","security.entitlement.apply"])
    with TemporaryDirectory() as d:
        svc=SecurityComplianceCenterService(Path(d)/"state.json",Path(d)/"audit.jsonl")
        role=svc.create_role(RoleRequest(
            role_id="portfolio-viewer",display_name="Portfolio Viewer",
            description="Read-only portfolio role",permissions=["portfolio.read"],
            privileged=False,actor=requester))
        assert role.role_id=="portfolio-viewer"

        identity=svc.create_identity(IdentityRequest(
            display_name="Research User",email="research@example.com",
            identity_type="HUMAN",roles=[],actor=requester))
        assert identity.status=="ACTIVE"

        change=svc.request_entitlement_change(EntitlementChangeRequest(
            identity_id=identity.identity_id,add_roles=["portfolio-viewer"],
            remove_roles=[],reason="Approved read-only portfolio access",
            confirmation_token="CONFIRM-SECURITY-123",actor=requester))
        assert change.status=="REQUESTED"

        try:
            svc.approve_entitlement_change(change.change_id,EntitlementApprovalRequest(
                decision="APPROVE",reason="Self approval attempt",
                confirmation_token="CONFIRM-SECURITY-123",actor=requester))
            raise AssertionError("Self approval should fail")
        except PermissionError:
            pass

        approved=svc.approve_entitlement_change(change.change_id,EntitlementApprovalRequest(
            decision="APPROVE",reason="Independent review completed",
            confirmation_token="CONFIRM-SECURITY-456",actor=approver))
        assert approved.status=="APPROVED"
        applied=svc.apply_entitlement_change(change.change_id,approver)
        assert applied.status=="APPLIED"
        assert "portfolio-viewer" in svc.list_identities()[0].roles

        secret=svc.register_secret_metadata(SecretMetadataRequest(
            secret_id="broker-api-key",display_name="Broker API Key",
            provider="ENV",environment="PAPER",reference="BROKER_API_KEY",
            last_rotated_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc)+timedelta(days=60),
            actor=requester))
        assert secret.value_visible is False
        assert secret.rotation_status=="CURRENT"

        controls=svc.compliance_controls()
        assert any(c.control_id=="SEC-001" and c.status=="PASS" for c in controls)
        review=svc.create_access_review(requester)
        assert review.identity_count==1

    print("All Milestone 33 Phase 8 Security & Compliance Center assertions passed.")

if __name__=="__main__":
    main()
