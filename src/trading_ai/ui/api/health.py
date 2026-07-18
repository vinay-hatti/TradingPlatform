from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "trading-ai-ui",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/readiness")
def readiness() -> dict[str, object]:
    adapters = RepositoryArtifactAdapters()
    scanner = adapters.scanner()
    return {
        "ready": True,
        "dashboard_available": True,
        "current_scan_available": scanner.available,
        "scanner_detail": scanner.detail,
        "project_root": str(adapters.root),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
