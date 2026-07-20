from trading_ai.research_workstation.portfolio_planning import (
    AllocationCandidateProfile,
    PortfolioAllocationEngine,
)


def candidate(
    candidate_id: str,
    symbol: str,
    sector: str,
    strategy: str,
    expected_return: float,
    delta: float,
) -> AllocationCandidateProfile:
    return AllocationCandidateProfile(
        candidate_id=candidate_id,
        symbol=symbol,
        sector=sector,
        strategy_name=strategy,
        requested_contracts=8,
        maximum_contracts=8,
        risk_per_contract=500.0,
        buying_power_per_contract=500.0,
        maximum_profit_per_contract=650.0,
        probability_of_profit=0.70,
        expected_return_pct=expected_return,
        annualized_volatility_pct=0.30,
        expected_shortfall_per_contract=325.0,
        liquidity_score=88.0,
        delta_per_contract=delta,
        gamma_per_contract=-0.8,
        theta_per_contract=2.5,
        vega_per_contract=-3.0,
        direction="BULLISH" if delta > 0 else "BEARISH",
    )


def main() -> None:
    candidates = (
        candidate(
            "AAA-1", "AAA", "Technology",
            "BULL_PUT_SPREAD", 0.20, 25.0,
        ),
        candidate(
            "BBB-1", "BBB", "Technology",
            "BULL_PUT_SPREAD", 0.18, 22.0,
        ),
        candidate(
            "CCC-1", "CCC", "Healthcare",
            "BEAR_CALL_SPREAD", 0.16, -20.0,
        ),
    )
    correlations = {
        ("AAA", "BBB"): 0.92,
        ("AAA", "CCC"): 0.15,
        ("BBB", "CCC"): 0.10,
    }

    profile = PortfolioAllocationEngine().allocate(
        account_equity=100_000.0,
        candidates=candidates,
        correlations=correlations,
    )

    assert profile.positions_allocated >= 2
    assert profile.exposure.total_risk <= 15_000.0
    assert profile.health.capital_utilization_pct <= 0.65
    assert profile.exposure.portfolio_delta != 0
    assert profile.exposure.portfolio_theta > 0
    assert "Technology" in profile.exposure.sector_exposure
    assert "Healthcare" in profile.exposure.sector_exposure
    assert any(
        "High correlation" in warning
        for warning in profile.warnings
    )
    assert all(
        decision.allocated_contracts <= 8
        for decision in profile.decisions
    )

    print(
        "All Milestone 34 Phase 3 Step 2 portfolio-allocation "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
