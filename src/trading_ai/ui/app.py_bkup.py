from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from trading_ai.ui.api.dashboard import router as dashboard_router
from trading_ai.ui.api.health import router as health_router
from trading_ai.ui.api.opportunities import router as opportunities_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading AI Institutional Workstation",
        version="31.3.0",
        description="Milestone 31 Phase 3 AI Opportunity Screener.",
    )
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(opportunities_router)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
