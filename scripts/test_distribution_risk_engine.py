import numpy as np

from trading_ai.strategy_engine.distribution_risk_policy import (
    DistributionRiskPolicy,
)
from trading_ai.strategy_engine.distribution_risk_service import (
    DistributionRiskService,
)


def print_profile(profile):
    print(
        f"\n========== "
        f"{profile.symbol} "
        f"{profile.strategy} =========="
    )

    print(
        f"Observations              : "
        f"{profile.observation_count}"
    )

    print(
        f"Historical VaR 95         : "
        f"${profile.historical_var:,.2f}"
    )

    print(
        f"Historical ES 95          : "
        f"${profile.historical_expected_shortfall:,.2f}"
    )

    print(
        f"Parametric VaR 95         : "
        f"${profile.parametric_var:,.2f}"
    )

    print(
        f"Parametric ES 95          : "
        f"${profile.parametric_expected_shortfall:,.2f}"
    )

    print(
        f"Historical VaR 99         : "
        f"${profile.historical_var_99:,.2f}"
    )

    print(
        f"Historical ES 99          : "
        f"${profile.historical_expected_shortfall_99:,.2f}"
    )

    print(
        f"Skewness                  : "
        f"{profile.skewness:.4f}"
    )

    print(
        f"Excess Kurtosis           : "
        f"{profile.excess_kurtosis:.4f}"
    )

    print(
        f"Downside Deviation        : "
        f"{profile.downside_deviation:.4%}"
    )

    print(
        f"Probability of Loss       : "
        f"{profile.probability_of_loss:.2%}"
    )

    print(
        f"Probability Large Loss    : "
        f"{profile.probability_of_large_loss:.2%}"
    )

    print(
        f"Maximum Drawdown          : "
        f"${profile.maximum_drawdown:,.2f}"
    )

    print(
        f"Maximum Drawdown %        : "
        f"{profile.maximum_drawdown_pct:.2%}"
    )

    print(
        f"Drawdown-at-Risk          : "
        f"{profile.drawdown_at_risk:.2%}"
    )

    print(
        f"Expected DD Shortfall     : "
        f"{profile.expected_drawdown_shortfall:.2%}"
    )

    print(
        f"Sortino Ratio             : "
        f"{profile.sortino_ratio}"
    )

    print(
        f"Omega Ratio               : "
        f"{profile.omega_ratio}"
    )

    print(
        f"Tail Risk Score           : "
        f"{profile.tail_risk_score:.2f}"
    )

    print(
        f"Tail Risk Grade           : "
        f"{profile.tail_risk_grade}"
    )

    print(
        f"Risk Severity             : "
        f"{profile.risk_severity}"
    )

    print(
        f"Allowed                   : "
        f"{profile.allowed}"
    )

    print(
        f"Rejections                : "
        f"{profile.rejection_reasons or '-'}"
    )

    print(
        f"Warnings                  : "
        f"{profile.warnings or '-'}"
    )


def main():
    rng = np.random.default_rng(
        42
    )

    normal_distribution = rng.normal(
        loc=75.0,
        scale=250.0,
        size=500,
    )

    negative_tail_distribution = np.concatenate(
        [
            rng.normal(
                loc=85.0,
                scale=180.0,
                size=470,
            ),
            rng.normal(
                loc=-1200.0,
                scale=350.0,
                size=30,
            ),
        ]
    )

    bounded_credit_distribution = np.concatenate(
        [
            np.full(
                350,
                150.0,
            ),
            rng.normal(
                loc=-250.0,
                scale=50.0,
                size=150,
            ),
        ]
    )

    policy = DistributionRiskPolicy(
        confidence_level=0.95,
        secondary_confidence_level=0.99,
        maximum_var_pct_of_capital=0.20,
        maximum_expected_shortfall_pct_of_capital=0.30,
        maximum_drawdown_at_risk_pct=0.40,
    )

    service = DistributionRiskService(
        policy=policy
    )

    normal_profile = (
        service.analyze_strategy(
            pnl_values=(
                normal_distribution
            ),
            capital_required=10000.0,
            initial_capital=100000.0,
            symbol="NORMAL",
            strategy="BULL_CALL_SPREAD",
        )
    )

    tail_profile = (
        service.analyze_strategy(
            pnl_values=(
                negative_tail_distribution
            ),
            capital_required=10000.0,
            initial_capital=100000.0,
            symbol="TAIL",
            strategy="SHORT_VOL",
        )
    )

    credit_profile = (
        service.analyze_strategy(
            pnl_values=(
                bounded_credit_distribution
            ),
            capital_required=3000.0,
            initial_capital=100000.0,
            symbol="CREDIT",
            strategy="IRON_CONDOR",
        )
    )

    print_profile(
        normal_profile
    )

    print_profile(
        tail_profile
    )

    print_profile(
        credit_profile
    )

    # ---------------------------------------------
    # Strategy-level assertions
    # ---------------------------------------------

    for profile in [
        normal_profile,
        tail_profile,
        credit_profile,
    ]:
        assert profile.valid is True
        assert profile.observation_count == 500
        assert profile.historical_var >= 0
        assert (
            profile
            .historical_expected_shortfall
            >= profile.historical_var
        )
        assert profile.historical_var_99 >= 0
        assert (
            profile
            .historical_expected_shortfall_99
            >= profile.historical_var_99
        )
        assert (
            0.0
            <= profile.probability_of_loss
            <= 1.0
        )
        assert (
            0.0
            <= profile.tail_risk_score
            <= 100.0
        )

    assert (
        tail_profile
        .historical_expected_shortfall
        > normal_profile
        .historical_expected_shortfall
    )

    assert (
        tail_profile.skewness
        < normal_profile.skewness
    )

    assert (
        tail_profile.excess_kurtosis
        > normal_profile.excess_kurtosis
    )

    assert (
        tail_profile.tail_risk_score
        < normal_profile.tail_risk_score
    )

    # ---------------------------------------------
    # Portfolio test
    # ---------------------------------------------

    position_1 = rng.normal(
        40.0,
        160.0,
        size=500,
    )

    position_2 = rng.normal(
        25.0,
        120.0,
        size=500,
    )

    position_3 = (
        -0.40 * position_1
        + rng.normal(
            10.0,
            100.0,
            size=500,
        )
    )

    pnl_matrix = np.column_stack(
        [
            position_1,
            position_2,
            position_3,
        ]
    )

    portfolio_profile = (
        service.analyze_portfolio(
            pnl_matrix=pnl_matrix,
            position_metadata=[
                {
                    "position_id": "P1",
                    "symbol": "AAPL",
                    "strategy":
                        "BULL_CALL_SPREAD",
                },
                {
                    "position_id": "P2",
                    "symbol": "MSFT",
                    "strategy":
                        "BULL_PUT_SPREAD",
                },
                {
                    "position_id": "P3",
                    "symbol": "JPM",
                    "strategy":
                        "BEAR_CALL_SPREAD",
                },
            ],
            initial_capital=100000.0,
            weights=[
                1.0,
                1.0,
                1.0,
            ],
        )
    )

    print(
        "\n========== PORTFOLIO TAIL RISK =========="
    )

    print(
        f"Portfolio VaR             : "
        f"${portfolio_profile.portfolio_var:,.2f}"
    )

    print(
        f"Portfolio ES              : "
        f"${portfolio_profile.portfolio_expected_shortfall:,.2f}"
    )

    print(
        f"VaR / Capital             : "
        f"{portfolio_profile.var_pct_of_capital:.2%}"
    )

    print(
        f"ES / Capital              : "
        f"{portfolio_profile.expected_shortfall_pct_of_capital:.2%}"
    )

    print(
        f"Largest VaR Contributor   : "
        f"{portfolio_profile.largest_var_contributor}"
    )

    print(
        f"Largest ES Contributor    : "
        f"{portfolio_profile.largest_es_contributor}"
    )

    print(
        f"Risk Concentration Score  : "
        f"{portfolio_profile.risk_concentration_score:.2f}"
    )

    print(
        f"Diversification Benefit   : "
        f"{portfolio_profile.diversification_benefit:.2%}"
    )

    for item in (
        portfolio_profile.contributions
    ):
        print(
            f"  {item.symbol:<6} "
            f"Component VaR="
            f"${item.component_var:>9.2f} "
            f"VaR Contribution="
            f"{item.var_contribution_pct:>7.2%} "
            f"ES Contribution="
            f"{item.expected_shortfall_contribution_pct:>7.2%}"
        )

    assert portfolio_profile.valid is True
    assert portfolio_profile.position_count == 3
    assert len(
        portfolio_profile.contributions
    ) == 3

    total_var_contribution = sum(
        item.var_contribution_pct
        for item
        in portfolio_profile.contributions
    )

    total_es_contribution = sum(
        item
        .expected_shortfall_contribution_pct
        for item
        in portfolio_profile.contributions
    )

    assert abs(
        total_var_contribution - 1.0
    ) < 0.01

    assert abs(
        total_es_contribution - 1.0
    ) < 0.01

    print(
        "\nAll distribution-risk assertions passed."
    )

    print(
        "============================================="
    )


if __name__ == "__main__":
    main()
