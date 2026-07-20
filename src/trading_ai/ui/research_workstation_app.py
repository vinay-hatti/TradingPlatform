from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from trading_ai.ui.api.research_scanner import router

def create_research_workstation_app():
    app = FastAPI(title="Trading AI Institutional Research Workstation", version="34.1.5")
    app.include_router(router)
    static = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")
    @app.get("/")
    def home():
        return FileResponse(static / "research_scanner.html")
    return app

app = create_research_workstation_app()
