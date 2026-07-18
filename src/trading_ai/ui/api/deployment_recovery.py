from fastapi import APIRouter, Depends, HTTPException

from trading_ai.ui.models.deployment_recovery import (
    BackupCreateRequest,
    DeploymentRecoveryState,
    PackageCreateRequest,
    PromotionRequest,
    RestoreRequest,
    RuntimeActionRequest,
)
from trading_ai.ui.services.deployment_recovery_service import (
    DeploymentRecoveryService,
)


router = APIRouter(
    prefix="/api/v1/deployment-recovery",
    tags=["deployment-recovery"],
)


def service() -> DeploymentRecoveryService:
    return DeploymentRecoveryService()


@router.get("", response_model=DeploymentRecoveryState)
def state(deployment: DeploymentRecoveryService = Depends(service)):
    return deployment.state()


@router.post("/packages")
def create_package(
    request: PackageCreateRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    return deployment.create_package(
        request.version,
        request.environment,
        request.requested_by,
    )


@router.post("/promotions")
def promote(
    request: PromotionRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    try:
        result = deployment.promote(
            request.package_id,
            request.source_environment,
            request.target_environment,
            request.requested_by,
            request.reason,
            request.confirmation_token,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Package not found")
    if result.status == "REJECTED":
        raise HTTPException(
            status_code=403,
            detail=result.model_dump(mode="json"),
        )
    return result


@router.post("/runtime/{name}/start")
def start_runtime(
    name: str,
    request: RuntimeActionRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    try:
        return deployment.start_runtime(name, request.confirmation_token)
    except KeyError:
        raise HTTPException(status_code=404, detail="Runtime not found")
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))


@router.post("/runtime/{name}/stop")
def stop_runtime(
    name: str,
    request: RuntimeActionRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    try:
        return deployment.stop_runtime(name, request.confirmation_token)
    except KeyError:
        raise HTTPException(status_code=404, detail="Runtime not found")
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))


@router.post("/runtime/{name}/restart")
def restart_runtime(
    name: str,
    request: RuntimeActionRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    try:
        return deployment.restart_runtime(name, request.confirmation_token)
    except KeyError:
        raise HTTPException(status_code=404, detail="Runtime not found")
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))


@router.post("/backups")
def create_backup(
    request: BackupCreateRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    return deployment.create_backup(request.actor, request.reason)


@router.post("/backups/{backup_id}/verify")
def verify_backup(
    backup_id: str,
    deployment: DeploymentRecoveryService = Depends(service),
):
    try:
        return deployment.verify_backup(backup_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Backup not found")


@router.post("/backups/{backup_id}/restore")
def restore_backup(
    backup_id: str,
    request: RestoreRequest,
    deployment: DeploymentRecoveryService = Depends(service),
):
    try:
        return deployment.restore_backup(
            backup_id,
            request.confirmation_token,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Backup not found")
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
