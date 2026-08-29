from trading_ai.research_workstation.portfolio_planning import (
    AllocationCandidateProfile,
    PortfolioAllocationEngine,
    portfolio_allocation_payload,
)


def main() -> None:
    candidate = AllocationCandidateProfile(
        candidate_id="AAA-BPS-1",
        symbol="AAA",
        sector="Technology",
        strategy_name="BULL_PUT_SPREAD",
        requested_contracts=10,
        maximum_contracts=10,
        risk_per_contract=320.0,
        buying_power_per_contract=320.0,
        maximum_profit_per_contract=400.0,
        probability_of_profit=0.72,
        expected_return_pct=0.18,
        annualized_volatility_pct=0.28,
        expected_shortfall_per_contract=210.0,
        liquidity_score=92.0,
        delta_per_contract=28.0,
        gamma_per_contract=-1.0,
        theta_per_contract=3.0,
        vega_per_contract=-4.0,
        direction="BULLISH",
    )

    profile = PortfolioAllocationEngine().allocate(
        account_equity=100_000.0,
        candidates=(candidate,),
    )

    assert profile.allowed is True
    assert profile.positions_allocated == 1
    assert profile.decisions[0].allocated_contracts > 0
    assert profile.decisions[0].allocated_contracts <= 10
    assert profile.exposure.total_risk <= 15_000.0
    assert profile.exposure.total_buying_power <= 65_000.0
    assert profile.health.portfolio_risk_pct <= 0.15
    assert profile.sizing_profiles[0].kelly_fraction > 0
    assert profile.sizing_profiles[0].liquidity_haircut == 0.92
    assert profile.metadata["step"] == 2

    payload = portfolio_allocation_payload(profile)
    assert payload["candidates_evaluated"] == 1
    assert payload["positions_allocated"] == 1
    assert payload["decisions"][0]["symbol"] == "AAA"

    print(
        "All Milestone 34 Phase 3 Step 2 position-sizing "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
