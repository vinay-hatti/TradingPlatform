from __future__ import annotations

from time import perf_counter
from uuid import uuid4
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .audit import ApiAuditEvent, JsonApiAuditStore, utc_now
from .config import ProductionApiSettings
from .router import router
from .service import ProductionApiService
from trading_ai.realtime_monitoring.service import RealtimeMonitoringService
from trading_ai.realtime_monitoring.router import router as realtime_router
from trading_ai.daily_scan_workstation.router import router as scanner_router
from trading_ai.daily_scan_workstation.service import DailyScanWorkstationService
from trading_ai.market_overview.service import MarketOverviewService
from trading_ai.market_overview.router import router as market_overview_router
from trading_ai.market_intelligence.service import MarketIntelligenceService
from trading_ai.market_intelligence.router import router as market_intelligence_router
from trading_ai.opportunity_domain.router import router as opportunity_router
from trading_ai.institutional_intelligence.router import router as institutional_intelligence_router
from trading_ai.advanced_trade_builder.router import router as advanced_trade_builder_router
from trading_ai.portfolio_intelligence.router import router as portfolio_intelligence_router
from trading_ai.performance_learning.router import router as performance_learning_router


def create_production_app(settings: ProductionApiSettings | None = None) -> FastAPI:
    resolved = settings or ProductionApiSettings.from_env()
    app = FastAPI(
        title="Trading AI Production API",
        version="43.0.0",
        description="Governed production API for portfolio, risk, execution, and position management.",
    )
    app.state.m40_settings = resolved
    app.state.m40_service = ProductionApiService(resolved)
    app.state.m40_audit = JsonApiAuditStore(resolved.artifact_root / "m40/api_audit.json")
    app.state.m42_service = RealtimeMonitoringService(resolved.artifact_root)
    app.state.m43_service = DailyScanWorkstationService(Path(__file__).resolve().parents[3], resolved.artifact_root)
    app.state.m45_market_overview_service = MarketOverviewService()
    app.state.m46_market_intelligence_service = MarketIntelligenceService()

    @app.middleware("http")
    async def request_governance(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})
        duration_ms = round((perf_counter() - started) * 1000.0, 3)
        response.headers["X-Request-ID"] = request_id
        event = ApiAuditEvent(
            event_id=uuid4().hex,
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            actor=request.headers.get("X-Actor"),
            occurred_at=utc_now(),
            metadata={"client": request.client.host if request.client else None},
        )
        app.state.m40_audit.append(event)
        return response

    app.include_router(router)
    app.include_router(realtime_router)
    app.include_router(scanner_router)
    app.include_router(market_overview_router)
    app.include_router(market_intelligence_router)
    app.include_router(opportunity_router)
    app.include_router(institutional_intelligence_router)
    app.include_router(advanced_trade_builder_router)
    app.include_router(portfolio_intelligence_router)
    app.include_router(performance_learning_router)

    @app.on_event("startup")
    async def start_m42(): await app.state.m42_service.start()

    @app.on_event("shutdown")
    async def stop_m42(): await app.state.m42_service.stop()
    return app


app = create_production_app()
