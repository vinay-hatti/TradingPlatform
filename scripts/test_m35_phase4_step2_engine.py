from datetime import date

from trading_ai.scanner.option_surface_analytics.contracts import (
    AggregateGovernanceStatus,
)
from trading_ai.scanner.option_surface_analytics.engine import (
    OptionFeatureInput,
    OptionSurfaceAnalyticsEngine,
)
from trading_ai.scanner.option_surface_analytics.policy import (
    OptionSurfaceAnalyticsPolicy,
)


def row(option_type, strike, delta, iv, oi=100, volume=20):
    return OptionFeatureInput(
        underlying_symbol="AAPL",
        quote_date=date(2026, 7, 20),
        expiry=date(2026, 8, 21),
        option_type=option_type,
        strike=strike,
        days_to_expiration=32,
        implied_volatility=iv,
        absolute_delta=delta,
        volume=volume,
        open_interest=oi,
        governance_status="READY",
    )


def main():
    policy = OptionSurfaceAnalyticsPolicy(
        minimum_contracts_per_expiration=4,
        minimum_strikes_per_expiration=3,
        minimum_open_interest_per_expiration=100,
        minimum_atm_term_points_for_ready=1,
    )
    engine = OptionSurfaceAnalyticsEngine(policy)

    rows = (
        row("PUT", 180, 0.25, 0.32),
        row("PUT", 190, 0.50, 0.28),
        row("CALL", 200, 0.50, 0.27),
        row("CALL", 210, 0.25, 0.29),
    )

    expirations, symbols = engine.build(rows)
    assert len(expirations) == 1
    assert len(symbols) == 1

    expiration = expirations[0]
    assert expiration.governance_status == AggregateGovernanceStatus.READY
    assert expiration.atm_implied_volatility == 0.275
    assert expiration.put_skew_25d_minus_atm == 0.045
    assert expiration.call_skew_25d_minus_atm == 0.015
    assert expiration.risk_reversal_25d == -0.03
    assert expiration.total_open_interest == 400
    assert expiration.top_5_open_interest_concentration == 1.0

    symbol = symbols[0]
    assert symbol.governance_status == AggregateGovernanceStatus.READY
    assert symbol.total_contract_count == 4
    assert symbol.total_open_interest == 400

    print("Milestone 35 Phase 4 Step 2 engine assertions passed.")


if __name__ == "__main__":
    main()
