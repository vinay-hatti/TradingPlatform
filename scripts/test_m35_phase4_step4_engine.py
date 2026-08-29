from trading_ai.scanner.option_surface_decision_integration.contracts import (
    SurfaceDecisionPolicy,
    SurfaceDecisionStatus,
)
from trading_ai.scanner.option_surface_decision_integration.engine import (
    OptionSurfaceDecisionEngine,
)


def main():
    engine = OptionSurfaceDecisionEngine(
        SurfaceDecisionPolicy(
            minimum_total_open_interest=1000,
            minimum_total_volume=10,
        )
    )

    profile = engine.evaluate(
        {
            "underlying_symbol": "AAPL",
            "quote_date": "2026-07-20",
            "governance_status": "READY",
            "expiration_count": "4",
            "total_contract_count": "100",
            "total_volume": "500",
            "total_open_interest": "25000",
            "nearest_atm_implied_volatility": "0.28",
            "farthest_atm_implied_volatility": "0.24",
            "atm_term_structure_slope": "-0.001",
            "aggregate_put_call_volume_ratio": "1.50",
            "aggregate_put_call_open_interest_ratio": "1.30",
        }
    )

    assert profile.decision_status == SurfaceDecisionStatus.ELIGIBLE
    assert profile.iv_term_structure_regime == "BACKWARDATION"
    assert profile.options_flow_bias == "PUT_BIASED"
    assert profile.liquidity_regime == "DEEP"
    assert profile.put_signal_adjustment > 0
    assert profile.call_signal_adjustment < 0
    assert profile.confidence_adjustment > 0

    blocked = engine.evaluate(
        {
            "underlying_symbol": "XYZ",
            "quote_date": "2026-07-20",
            "governance_status": "EXCLUDED",
            "expiration_count": "0",
            "total_contract_count": "0",
            "total_volume": "0",
            "total_open_interest": "0",
        }
    )
    assert blocked.decision_status == SurfaceDecisionStatus.BLOCKED
    assert blocked.confidence_adjustment == -1.0

    print("Milestone 35 Phase 4 Step 4 engine assertions passed.")


if __name__ == "__main__":
    main()
