from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.services.opportunity_screener_service import (
    OpportunityScreenerService,
)
from trading_ai.ui.api.opportunities import service as opportunity_service_dependency
from trading_ai.ui.app import create_app


def main() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        reports.mkdir(parents=True)

        path = reports / "scanner_results_20260718.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "symbol",
                    "signal",
                    "strategy",
                    "rank_score",
                    "probability_of_profit",
                    "expected_value",
                    "regime",
                    "contract_ticker",
                    "spread_pct",
                    "volume",
                    "open_interest",
                    "liquidity_score",
                    "status",
                ],
            )
            writer.writeheader()
            writer.writerow({
                "symbol": "SPY",
                "signal": "CALL",
                "strategy": "Long Call",
                "rank_score": "94",
                "probability_of_profit": "0.82",
                "expected_value": "3.4",
                "regime": "BULL_TREND",
                "contract_ticker": "SPY-CALL",
                "spread_pct": "0.12",
                "volume": "250",
                "open_interest": "1200",
                "liquidity_score": "96",
                "status": "ACCEPTED",
            })
            writer.writerow({
                "symbol": "QQQ",
                "signal": "PUT",
                "strategy": "Long Put",
                "rank_score": "88",
                "probability_of_profit": "0.73",
                "expected_value": "2.1",
                "regime": "BEAR_TRANSITION",
                "contract_ticker": "QQQ-PUT",
                "spread_pct": "0.18",
                "volume": "180",
                "open_interest": "900",
                "liquidity_score": "90",
                "status": "ACCEPTED",
            })

        screener = OpportunityScreenerService(
            RepositoryArtifactAdapters(root),
            stale_after_seconds=999999,
        )

        direct_result = screener.query(min_score=90)
        assert direct_result.filtered_records == 1
        assert direct_result.records[0].symbol == "SPY"
        assert direct_result.records[0].probability_of_profit == 0.82

        app = create_app()

        # FastAPI stores the dependency callable object at route-registration
        # time. Override that exact original object rather than replacing the
        # module attribute after the router has already been created.
        app.dependency_overrides[opportunity_service_dependency] = (
            lambda: screener
        )

        client = TestClient(app)

        response = client.get("/api/v1/opportunities?min_score=80")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total_records"] == 2, payload
        assert payload["filtered_records"] == 2, payload
        assert [item["symbol"] for item in payload["records"]] == [
            "SPY",
            "QQQ",
        ], payload

        filtered = client.get(
            "/api/v1/opportunities?direction=CALL&min_score=90"
        )
        assert filtered.status_code == 200, filtered.text
        filtered_payload = filtered.json()
        assert filtered_payload["filtered_records"] == 1, filtered_payload
        assert filtered_payload["records"][0]["symbol"] == "SPY"

        export = client.get("/api/v1/opportunities/export.csv")
        assert export.status_code == 200, export.text
        assert "SPY" in export.text
        assert "QQQ" in export.text

        app.dependency_overrides.clear()

    print(
        "All Milestone 31 Phase 3 opportunity-screener assertions passed."
    )


if __name__ == "__main__":
    main()
