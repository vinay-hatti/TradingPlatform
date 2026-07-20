from fastapi import APIRouter, Depends, HTTPException

from trading_ai.ui.models.paper_commands import GovernedActor
from trading_ai.ui.models.security_compliance_center import (
    EntitlementApprovalRequest,
    EntitlementChangeRequest,
    IdentityRequest,
    RoleRequest,
    SecretMetadataRequest,
    SessionRevokeRequest,
)
from trading_ai.ui.services.security_compliance_center_service import (
    SecurityComplianceCenterService,
)

router = APIRouter(prefix="/api/v1/security", tags=["security-compliance"])

def service():
    return SecurityComplianceCenterService()

@router.get("/identities")
def identities(svc=Depends(service)):
    return svc.list_identities()

@router.post("/identities")
def create_identity(request: IdentityRequest, svc=Depends(service)):
    try:
        return svc.create_identity(request)
    except PermissionError as error:
        raise HTTPException(403, str(error))

@router.get("/roles")
def roles(svc=Depends(service)):
    return svc.list_roles()

@router.post("/roles")
def create_role(request: RoleRequest, svc=Depends(service)):
    try:
        return svc.create_role(request)
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))

@router.get("/entitlement-changes")
def entitlement_changes(svc=Depends(service)):
    return svc.list_entitlement_changes()

@router.post("/entitlement-changes")
def request_entitlement_change(request: EntitlementChangeRequest, svc=Depends(service)):
    try:
        return svc.request_entitlement_change(request)
    except KeyError:
        raise HTTPException(404, "Identity not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))

@router.post("/entitlement-changes/{change_id}/approval")
def approve_entitlement_change(
    change_id: str,
    request: EntitlementApprovalRequest,
    svc=Depends(service),
):
    try:
        return svc.approve_entitlement_change(change_id, request)
    except KeyError:
        raise HTTPException(404, "Entitlement change not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))

@router.post("/entitlement-changes/{change_id}/apply")
def apply_entitlement_change(
    change_id: str,
    actor: GovernedActor,
    svc=Depends(service),
):
    try:
        return svc.apply_entitlement_change(change_id, actor)
    except KeyError:
        raise HTTPException(404, "Entitlement change or identity not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))

@router.get("/sessions")
def sessions(svc=Depends(service)):
    return svc.list_sessions()

@router.post("/sessions/{session_id}/revoke")
def revoke_session(
    session_id: str,
    request: SessionRevokeRequest,
    svc=Depends(service),
):
    try:
        return svc.revoke_session(session_id, request)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))

@router.get("/secrets")
def secrets(svc=Depends(service)):
    return svc.list_secret_metadata()

@router.post("/secrets")
def register_secret_metadata(
    request: SecretMetadataRequest,
    svc=Depends(service),
):
    try:
        return svc.register_secret_metadata(request)
    except PermissionError as error:
        raise HTTPException(403, str(error))

@router.get("/compliance-controls")
def compliance_controls(svc=Depends(service)):
    return svc.compliance_controls()

@router.post("/access-reviews")
def create_access_review(actor: GovernedActor, svc=Depends(service)):
    try:
        return svc.create_access_review(actor)
    except PermissionError as error:
        raise HTTPException(403, str(error))
