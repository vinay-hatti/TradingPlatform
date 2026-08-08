from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access

from .publication import StockScannerPublicationService

router = APIRouter(prefix="/api/v1/stock-intelligence", tags=["stock-intelligence"])


def envelope(request: Request, data, **metadata):
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)


@router.get("/candidates", response_model=ApiEnvelope)
def list_candidates(
    request: Request,
    publication_name: str = "current_stock_intelligence",
    category: str | None = None,
    direction: str | None = None,
    structure: str | None = None,
    search: str | None = None,
    min_score: float = Query(0, ge=0, le=100),
    min_confidence: float = Query(0, ge=0, le=100),
    limit: int = Query(2000, ge=1, le=5000),
    _: str = Depends(require_access),
):
    with SessionLocal() as session:
        publication, values = StockScannerPublicationService(session).candidates(
            publication_name=publication_name,
            category=category,
            direction=direction,
            structure=structure,
            search=search,
            min_score=min_score,
            min_confidence=min_confidence,
            limit=limit,
        )
        metadata = {
            "publication": None if publication is None else {
                "publication_id": publication.id,
                "publication_name": publication.publication_name,
                "scanner_run_id": publication.scanner_run_id,
                "status": publication.status,
                "snapshot_timestamp": publication.snapshot_timestamp,
                "source": (publication.payload_json or {}).get("source", "persisted_polygon_price_history"),
                "timeframes": (publication.payload_json or {}).get("timeframes", []),
                "context_sources": (publication.payload_json or {}).get("context_sources", []),
            },
            "count": len(values),
        }
        return envelope(request, values, **metadata)


@router.get("/candidates/{candidate_id}", response_model=ApiEnvelope)
def get_candidate(candidate_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        value = StockScannerPublicationService(session).candidate(candidate_id)
        if value is None:
            raise HTTPException(404, "Stock Intelligence candidate not found")
        return envelope(request, value)
