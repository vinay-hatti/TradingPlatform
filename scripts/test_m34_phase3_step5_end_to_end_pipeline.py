from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.research_workstation.phase3_pipeline import (
    Phase3PipelineEngine,
)


def manifest():
    as_of = date(2026, 7, 19)
    expiration = as_of + timedelta(days=33)
    return {
        "trade": {
            "trade_id": "PIPELINE-001",
            "symbol": "AAPL",
            "sector": "TECHNOLOGY",
            "strategy_name": "BULL_PUT_SPREAD",
            "direction": "BULLISH",
            "requested_contracts": 2,
            "maximum_profit_per_contract": 400.0,
            "maximum_loss_per_contract": 320.0,
            "probability_of_profit": 0.72,
            "breakeven_points": [198.20],
            "quantity_ratios": [1, 1],
            "legs": [
                {
                    "expiration": expiration.isoformat(),
                    "option_type": "PUT",
                    "side": "SHORT",
                    "strike": 200.0,
                    "bid": 2.45,
                    "ask": 2.55,
                    "mark": 2.50,
                    "open_interest": 8500,
                    "volume": 1400,
                    "delta": -0.28,
                    "gamma": 0.04,
                    "theta": -0.08,
                    "vega": 0.12,
                },
                {
                    "expiration": expiration.isoformat(),
                    "option_type": "PUT",
                    "side": "LONG",
                    "strike": 195.0,
                    "bid": 0.65,
                    "ask": 0.75,
                    "mark": 0.70,
                    "open_interest": 6200,
                    "volume": 900,
                    "delta": -0.16,
                    "gamma": 0.03,
                    "theta": -0.05,
                    "vega": 0.09,
                },
            ],
        },
        "account": {"account_equity": 100000.0},
        "portfolio_planning": {
            "candidate_id": "PIPELINE-001-CANDIDATE",
            "maximum_contracts": 2,
            "expected_return_pct": 0.10,
            "annualized_volatility_pct": 0.24,
            "expected_shortfall_per_contract": 160.0,
            "liquidity_score": 92.0,
            "greeks_per_contract": {
                "delta": 12.0,
                "gamma": -1.0,
                "theta": 3.0,
                "vega": -4.0,
            },
        },
        "lifecycle": {
            "as_of_date": as_of.isoformat(),
            "confidence": 0.82,
            "event_date": None,
        },
        "governance": {
            "broker_ready": True,
            "compliance_cleared": True,
            "event_risk_present": False,
        },
    }


def main() -> None:
    with TemporaryDirectory() as tmp:
        result = Phase3PipelineEngine().run(
            manifest=manifest(),
            output_directory=tmp,
        )

        required = (
            result.trade_construction_report,
            result.portfolio_allocation_report,
            result.trade_lifecycle_report,
            result.pretrade_governance_report,
            result.dashboard_json_report,
            result.dashboard_html_report,
            result.pipeline_report,
        )
        assert all(Path(path).exists() for path in required)
        assert result.trade_id == "PIPELINE-001"
        assert result.symbol == "AAPL"
        assert result.strategy_name == "BULL_PUT_SPREAD"
        assert result.overall_status in {
            "READY",
            "READY_WITH_WARNINGS",
            "REVIEW_REQUIRED",
            "BLOCKED",
        }
        assert result.approval_status
        assert "Milestone 34 Phase 3" in Path(
            result.dashboard_html_report
        ).read_text(encoding="utf-8")

    print(
        "All Milestone 34 Phase 3 Step 5 end-to-end pipeline "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
