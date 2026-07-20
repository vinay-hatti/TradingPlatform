from fastapi import APIRouter, Depends, HTTPException

from trading_ai.ui.models.strategy_studio import (
    ExperimentRequest,
    PromotionRequest,
    ShadowDeploymentRequest,
    StrategyDraftRequest,
)
from trading_ai.ui.services.strategy_studio_service import StrategyStudioService

router = APIRouter(prefix="/api/v1/strategy-studio", tags=["strategy-studio"])

def service():
    return StrategyStudioService()

@router.post("/versions")
def create_version(request: StrategyDraftRequest, svc=Depends(service)):
    return svc.create_version(request)

@router.get("/versions")
def list_versions(strategy_id: str | None = None, svc=Depends(service)):
    return svc.list_versions(strategy_id)

@router.get("/versions/{version_id}")
def get_version(version_id: str, svc=Depends(service)):
    try:
        return svc.get_version(version_id)
    except KeyError:
        raise HTTPException(404, "Strategy version not found")

@router.post("/shadow-deployments")
def create_shadow(request: ShadowDeploymentRequest, svc=Depends(service)):
    try:
        return svc.create_shadow(request)
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))

@router.get("/shadow-deployments")
def list_shadows(svc=Depends(service)):
    return svc.list_deployments()

@router.post("/experiments")
def create_experiment(request: ExperimentRequest, svc=Depends(service)):
    try:
        return svc.create_experiment(request)
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))

@router.get("/experiments")
def list_experiments(svc=Depends(service)):
    return svc.list_experiments()

@router.post("/experiments/{experiment_id}/promote")
def promote(experiment_id: str, request: PromotionRequest, svc=Depends(service)):
    try:
        return svc.promote(experiment_id, request)
    except KeyError:
        raise HTTPException(404, "Experiment not found")
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(422, str(error))
