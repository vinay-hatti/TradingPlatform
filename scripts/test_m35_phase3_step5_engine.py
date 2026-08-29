from datetime import date

from trading_ai.scanner.options_market_data_readiness.contracts import (
    GovernanceStatus,
)
from trading_ai.scanner.options_market_data_readiness.engine import (
    CoverageInput,
    OptionDataReadinessEngine,
    QualityInput,
)


def main():
    profiles = OptionDataReadinessEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        coverage_rows=(
            CoverageInput(
                symbol="AAPL",
                status="READY",
                score=0.90,
                contract_count=100,
                expiration_count=3,
                distinct_strike_count=30,
            ),
            CoverageInput(
                symbol="SMALL",
                status="REVIEW",
                score=0.65,
                contract_count=5,
                expiration_count=1,
                distinct_strike_count=5,
            ),
            CoverageInput(
                symbol="NONE",
                status="FAILED",
                score=0.0,
                contract_count=0,
                expiration_count=0,
                distinct_strike_count=0,
            ),
        ),
        quality_rows=(
            QualityInput(
                symbol="AAPL",
                status="READY",
                score=1.0,
                quote_data_observed=False,
            ),
            QualityInput(
                symbol="SMALL",
                status="READY",
                score=1.0,
                quote_data_observed=False,
            ),
            QualityInput(
                symbol="NONE",
                status="FAILED",
                score=0.0,
                quote_data_observed=False,
            ),
        ),
    )

    aapl = next(p for p in profiles if p.symbol == "AAPL")
    small = next(p for p in profiles if p.symbol == "SMALL")
    none = next(p for p in profiles if p.symbol == "NONE")

    assert aapl.readiness_status == GovernanceStatus.READY
    assert aapl.readiness_score == 0.95
    assert aapl.provider_capability_limited is True

    assert small.readiness_status == GovernanceStatus.REVIEW
    assert none.readiness_status == GovernanceStatus.FAILED

    print("Milestone 35 Phase 3 Step 5 engine assertions passed.")


if __name__ == "__main__":
    main()
