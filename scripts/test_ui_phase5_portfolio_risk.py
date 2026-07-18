from __future__ import annotations

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.api.portfolio_risk import service as portfolio_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.services.portfolio_risk_service import PortfolioRiskService


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        paper_dir = root / "reports/paper_trading"
        risk_dir = root / "reports/risk"
        paper_dir.mkdir(parents=True)
        risk_dir.mkdir(parents=True)

        (paper_dir / "positions.json").write_text(
            json.dumps({
                "positions": [
                    {
                        "symbol": "SPY",
                        "strategy": "LONG_CALL",
                        "direction": "CALL",
                        "quantity": 2,
                        "entry_price": 4.0,
                        "current_price": 5.0,
                        "multiplier": 100,
                        "delta": 0.55,
                        "gamma": 0.03,
                        "theta": -0.08,
                        "vega": 0.11,
                        "status": "OPEN",
                    },
                    {
                        "symbol": "QQQ",
                        "strategy": "LONG_PUT",
                        "direction": "PUT",
                        "quantity": 1,
                        "entry_price": 6.0,
                        "current_price": 5.5,
                        "multiplier": 100,
                        "delta": -0.48,
                        "gamma": 0.02,
                        "theta": -0.07,
                        "vega": 0.10,
                        "status": "OPEN",
                    },
                ]
            }),
            encoding="utf-8",
        )

        (risk_dir / "risk_snapshot.json").write_text(
            json.dumps({
                "capital": 10000,
                "cash": 8450,
                "risk": {
                    "max_drawdown_pct": 4.2,
                    "value_at_risk": 325,
                    "expected_shortfall": 460,
                    "buying_power_utilization_pct": 15.5,
                    "utilization_pct": 42,
                },
            }),
            encoding="utf-8",
        )

        service = PortfolioRiskService(
            RepositoryArtifactAdapters(root),
            stale_after_seconds=999999,
        )
        direct = service.get()

        assert direct.available is True
        assert direct.summary.open_positions == 2
        assert math.isclose(
            direct.summary.unrealized_pnl,
            150.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        assert math.isclose(
            direct.risk.portfolio_delta,
            0.62,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        assert math.isclose(
            direct.risk.portfolio_gamma,
            0.08,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        assert math.isclose(
            direct.risk.portfolio_theta,
            -0.23,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        assert math.isclose(
            direct.risk.portfolio_vega,
            0.32,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        assert direct.risk.max_drawdown_pct == 4.2
        assert len(direct.limits) >= 5

        app = create_app()
        app.dependency_overrides[portfolio_dependency] = lambda: service
        response = TestClient(app).get("/api/v1/portfolio-risk")
        assert response.status_code == 200, response.text
        payload = response.json()

        assert payload["summary"]["open_positions"] == 2
        assert math.isclose(
            payload["risk"]["portfolio_delta"],
            0.62,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        assert payload["risk"]["risk_level"] in {
            "NORMAL",
            "ELEVATED",
            "CRITICAL",
        }

        app.dependency_overrides.clear()

    print(
        "All corrected Milestone 31 Phase 5 Portfolio and Risk "
        "Cockpit assertions passed."
    )


if __name__ == "__main__":
    main()
