from trading_ai.research_workstation.portfolio_planning import (
    AllocationCandidateProfile,
    PortfolioAllocationEngine,
)


def main() -> None:
    illiquid = AllocationCandidateProfile(
        candidate_id="RISK-1",
        symbol="RISK",
        sector="Speculative",
        strategy_name="NAKED_SHORT_CALL",
        requested_contracts=50,
        maximum_contracts=50,
        risk_per_contract=50_000.0,
        buying_power_per_contract=50_000.0,
        maximum_profit_per_contract=200.0,
        probability_of_profit=0.40,
        expected_return_pct=-0.15,
        annualized_volatility_pct=1.20,
        expected_shortfall_per_contract=45_000.0,
        liquidity_score=10.0,
        delta_per_contract=-60.0,
        gamma_per_contract=-5.0,
        theta_per_contract=1.0,
        vega_per_contract=-12.0,
        direction="BEARISH",
    )

    profile = PortfolioAllocationEngine().allocate(
        account_equity=25_000.0,
        candidates=(illiquid,),
    )

    assert profile.allowed is False
    assert profile.positions_allocated == 0
    assert profile.rejection_reasons
    assert profile.health.risk_severity in {"HIGH", "CRITICAL"}
    assert profile.decisions[0].allocation_status == "REJECTED"
    assert profile.sizing_profiles[0].recommended_contracts == 0

    print(
        "Milestone 34 Phase 3 Step 2 portfolio-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
