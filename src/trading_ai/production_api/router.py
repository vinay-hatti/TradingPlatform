from __future__ import annotations

from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .models import ApiEnvelope, WorkflowRunRequest, WorkflowRunResult
from .security import require_access, require_mutation_access
from .service import ProductionApiService

router = APIRouter(prefix="/api/v1/platform", tags=["production-platform"])


def service(request: Request) -> ProductionApiService:
    return request.app.state.m40_service


def envelope(request: Request, data, **metadata) -> ApiEnvelope:
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)


@router.get("/health", response_model=ApiEnvelope)
def health(request: Request):
    return envelope(request, {"service": "trading-ai-production-api", "milestone": 40, "status": "UP"})


@router.get("/readiness", response_model=ApiEnvelope)
def readiness(request: Request, response: Response, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    ready, details = svc.readiness()
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return envelope(request, {"ready": ready, "components": details})


@router.get("/overview", response_model=ApiEnvelope)
def overview(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    state = svc.platform_state()
    summary = {
        name: {
            "exists": doc.exists,
            "stale": doc.stale,
            "modified_at": doc.modified_at,
            "age_seconds": doc.age_seconds,
            "path": str(doc.path),
        }
        for name, doc in state.items()
    }
    return envelope(request, summary)


def artifact_response(request: Request, doc):
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {doc.path}")
    return envelope(request, doc.payload, artifact_path=str(doc.path), stale=doc.stale, age_seconds=doc.age_seconds)


@router.get("/portfolio", response_model=ApiEnvelope)
def portfolio(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    return artifact_response(request, svc.artifact(svc.settings.portfolio_registry_file))


@router.get("/risk", response_model=ApiEnvelope)
def risk(request: Request, _: str = Depends(require_access)):
    """Compatibility view backed by canonical Portfolio Intelligence data."""
    from trading_ai.database.session import SessionLocal
    from trading_ai.portfolio_intelligence.repository import PortfolioRepository
    from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService

    with SessionLocal() as session:
        repo = PortfolioRepository(session)
        positions = repo.list(portfolio_id="PAPER-PRIMARY")
        active = [item for item in positions if item.state not in ("CLOSED", "CANCELLED")]
        snapshot = repo.latest_snapshot("PAPER-PRIMARY")
        blocking = [item.position_id for item in active if float((item.health_json or {}).get("score", 100)) < 40]
        recommendations = []
        for item in active:
            decision = item.decision_json or {}
            action = str(decision.get("action", "HOLD"))
            if action != "HOLD":
                recommendations.append(f"{item.symbol}: {action} — {decision.get('reason', 'Review position intelligence')}")
        payload = {
            "portfolio_id": "PAPER-PRIMARY",
            "risk_status": "CRITICAL" if blocking else "REVIEW" if recommendations else "READY",
            "status": "CRITICAL" if blocking else "REVIEW" if recommendations else "READY",
            "trading_control": "BLOCK_NEW_RISK" if blocking else "ALLOW_GOVERNED_RISK",
            "allow_new_risk": not blocking,
            "blocking_breach_ids": blocking,
            "recommendations": recommendations or ["No active governed risk intervention."],
            "active_position_count": len(active),
            "positions": [PortfolioIntelligenceService.dto(item) for item in active],
            "portfolio_snapshot": ({"snapshot_id": snapshot.snapshot_id, **snapshot.payload_json} if snapshot else None),
        }
        return envelope(request, payload, source="canonical_portfolio_intelligence", compatibility_alias=True)


@router.get("/execution", response_model=ApiEnvelope)
def execution(request: Request, _: str = Depends(require_access)):
    """Compatibility alias for the canonical database-backed OMS queue.

    Milestone 59 retired the legacy reports/m38/execution_queue.json artifact as
    the workstation source. Keeping this endpoint database-backed prevents old
    bookmarks and cached frontend bundles from failing while users migrate to
    /api/v1/execution-workspace/intents.
    """
    from trading_ai.database.session import SessionLocal
    from trading_ai.execution_workspace.repository import ExecutionIntentRepository
    from trading_ai.execution_workspace.service import ExecutionWorkspaceService

    with SessionLocal() as session:
        items = ExecutionIntentRepository(session).list(portfolio_id="PAPER-PRIMARY")
        return envelope(
            request,
            [ExecutionWorkspaceService.dto(item) for item in items],
            count=len(items),
            source="canonical_execution_intents",
            compatibility_alias=True,
        )


@router.get("/positions", response_model=ApiEnvelope)
def positions(request: Request, _: str = Depends(require_access)):
    """Compatibility view backed by canonical managed positions."""
    from trading_ai.database.session import SessionLocal
    from trading_ai.portfolio_intelligence.repository import PortfolioRepository
    from trading_ai.portfolio_intelligence.service import PortfolioIntelligenceService

    with SessionLocal() as session:
        items = PortfolioRepository(session).list(portfolio_id="PAPER-PRIMARY")
        data = [PortfolioIntelligenceService.dto(item) for item in items]
        return envelope(request, data, count=len(data), source="canonical_managed_positions", compatibility_alias=True)


@router.get("/exit-instructions", response_model=ApiEnvelope)
def exits(request: Request, _: str = Depends(require_access)):
    """Compatibility view derived from canonical Portfolio Decision Intelligence."""
    from trading_ai.database.session import SessionLocal
    from trading_ai.portfolio_intelligence.repository import PortfolioRepository

    with SessionLocal() as session:
        items = PortfolioRepository(session).list(portfolio_id="PAPER-PRIMARY")
        instructions = []
        for item in items:
            if item.state in ("CLOSED", "CANCELLED"):
                continue
            decision = item.decision_json or {}
            action = str(decision.get("action", "HOLD"))
            instructions.append({
                "position_id": item.position_id,
                "symbol": item.symbol,
                "strategy": item.strategy,
                "action": action,
                "quantity": None,
                "order_type": "GOVERNED_POSITION_ACTION",
                "status": item.state,
                "urgency": decision.get("priority", "LOW"),
                "confidence": decision.get("confidence"),
                "reason": decision.get("reason"),
                "expected_benefit": decision.get("expected_benefit"),
                "risk_impact": decision.get("risk_impact"),
                "position_version": item.version,
            })
        return envelope(request, instructions, count=len(instructions), source="canonical_position_decisions", compatibility_alias=True)


@router.post("/workflows/{workflow}", response_model=ApiEnvelope)
def run_workflow(workflow: str, payload: WorkflowRunRequest, request: Request, actor: str = Depends(require_mutation_access), svc: ProductionApiService = Depends(service)):
    try:
        result = svc.run_workflow(workflow, payload.arguments)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown workflow") from exc
    if not result.accepted:
        raise HTTPException(status_code=409, detail=result.model_dump(mode="json"))
    return envelope(request, result.model_dump(mode="json"), actor=actor, requested_by=payload.requested_by, reason=payload.reason)
