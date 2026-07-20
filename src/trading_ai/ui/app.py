from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from trading_ai.ui.api.admin_runtime import router as admin_runtime_router
from trading_ai.ui.api.auth_session import router as auth_session_router
from trading_ai.ui.api.dashboard import router as dashboard_router
from trading_ai.ui.api.deployment_recovery import router as deployment_recovery_router
from trading_ai.ui.api.execution_console import router as execution_router
from trading_ai.ui.api.health import router as health_router
from trading_ai.ui.api.observability import router as observability_router
from trading_ai.ui.api.opportunities import router as opportunities_router
from trading_ai.ui.api.paper_commands import router as paper_commands_router
from trading_ai.ui.api.paper_execution import router as paper_execution_router
from trading_ai.ui.api.portfolio_risk import router as portfolio_risk_router
from trading_ai.ui.api.reporting_audit import router as reporting_audit_router
from trading_ai.ui.api.symbols import router as symbols_router
from trading_ai.ui.api.workstation_release import router as workstation_release_router
from trading_ai.ui.api.workspaces import router as workspaces_router
from trading_ai.ui.api.option_chain import router as option_chain_router
from trading_ai.ui.api.professional_order_entry import router as professional_order_entry_router
from trading_ai.ui.api.interactive_portfolio import router as interactive_portfolio_router
from trading_ai.ui.api.research_workbench import router as research_workbench_router
from trading_ai.ui.api.strategy_studio import router as strategy_studio_router
from trading_ai.ui.api.operations_command_center import router as operations_command_center_router
from trading_ai.ui.api.security_compliance_center import router as security_compliance_center_router
from trading_ai.ui.api.executive_reporting import router as executive_reporting_router
from trading_ai.ui.api.ui_resilience import router as ui_resilience_router
from trading_ai.ui.api.local_admin_session import router as local_admin_session_router
from trading_ai.ui.observability.middleware import ObservabilityMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading AI Institutional Workstation",
        version="33.10.1",
        description=(
            "Milestone 32 Phase 4 Deployment Packaging, Environment Promotion, "
            "Runtime Supervision, Backup, and Recovery."
        ),
    )
    app.add_middleware(ObservabilityMiddleware)

    for router in (
        health_router,
        dashboard_router,
        opportunities_router,
        symbols_router,
        portfolio_risk_router,
        execution_router,
        reporting_audit_router,
        admin_runtime_router,
        auth_session_router,
        workstation_release_router,
  workspaces_router,
  option_chain_router,
  professional_order_entry_router,
  interactive_portfolio_router,
  research_workbench_router,
  strategy_studio_router,
  operations_command_center_router,
  security_compliance_center_router,
  executive_reporting_router,
  ui_resilience_router,
  local_admin_session_router,
        paper_commands_router,
        paper_execution_router,
        observability_router,
        deployment_recovery_router,
    ):
        app.include_router(router)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
