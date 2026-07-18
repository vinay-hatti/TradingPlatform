from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from trading_ai.ui.models.observability import (
    AlertAcknowledgeRequest,
    ObservabilityState,
)
from trading_ai.ui.observability.metrics_registry import MetricsRegistry
from trading_ai.ui.services.observability_service import ObservabilityService


router = APIRouter(
    prefix="/api/v1/observability",
    tags=["observability"],
)


def service() -> ObservabilityService:
    return ObservabilityService()


@router.get("", response_model=ObservabilityState)
def state(observability: ObservabilityService = Depends(service)):
    return observability.state()


@router.get("/health/live")
def liveness(observability: ObservabilityService = Depends(service)):
    state = observability.state()
    return {
        "status": state.summary.liveness_status,
        "generated_at": state.generated_at,
    }


@router.get("/health/ready")
def readiness(observability: ObservabilityService = Depends(service)):
    state = observability.state()
    if state.summary.readiness_status == "UNHEALTHY":
        raise HTTPException(
            status_code=503,
            detail=state.model_dump(mode="json"),
        )
    return {
        "status": state.summary.readiness_status,
        "checks": [
            check.model_dump(mode="json")
            for check in state.health_checks
            if check.required
        ],
    }


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return MetricsRegistry.shared().prometheus_text()


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(
    alert_id: str,
    request: AlertAcknowledgeRequest,
    observability: ObservabilityService = Depends(service),
):
    try:
        return observability.acknowledge(
            alert_id,
            request.actor,
            request.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert not found")
