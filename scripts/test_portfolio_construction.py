from types import SimpleNamespace

from trading_ai.strategy_engine.institutional_opportunity import (
    InstitutionalOpportunity,
)
from trading_ai.strategy_engine.institutional_ranked_opportunity import (
    InstitutionalRankedOpportunity,
)
from trading_ai.strategy_engine.portfolio_risk_limits import (
    PortfolioRiskLimits,
)
from trading_ai.strategy_engine.portfolio_service import (
    PortfolioService,
)


def ranked_opportunity(
    rank,
    symbol,
    strategy,
    direction,
    ranking_score,
    capital_required,
    maximum_loss,
    expected_profit,
    sector,
    correlation_group,
    delta,
    theta,
    vega,
    selected=True,
    allowed=True,
    readiness="LIVE_CANDIDATE",
):
    greeks_profile = SimpleNamespace(
        net_delta=delta,
        net_gamma=0.02,
        net_theta=theta,
        net_vega=vega,
        net_rho=0.05,
    )

    opportunity = InstitutionalOpportunity(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        market_regime=(
            "BULL_TREND"
            if direction == "CALL"
            else (
                "BEAR_TREND"
                if direction == "PUT"
                else "SIDEWAYS"
            )
        ),
        strategy_score=ranking_score,
        allowed=allowed,
        readiness=readiness,
        recommendation=readiness,
        expected_return_pct=(
            expected_profit / capital_required
            if capital_required > 0
            else 0.0
        ),
        expected_profit=expected_profit,
        maximum_loss=maximum_loss,
        capital_required=capital_required,
        probability_of_profit=0.68,
        liquidity_score=88.0,
        execution_score=84.0,
        greeks_score=82.0,
        expected_move_score=80.0,
        data_confidence_score=82.0,
        risk_reward_score=78.0,
        portfolio_fit_score=80.0,
        expiry="2026-08-21",
        dte=30,
        premium_type="CREDIT",
        risk_profile="DEFINED_RISK",
        complexity="MULTI_LEG",
        sector=sector,
        correlation_group=correlation_group,
        contracts=1,
        rank_eligible=allowed,
        greeks_profile=greeks_profile,
    )

    return InstitutionalRankedOpportunity(
        rank=rank,
        opportunity=opportunity,
        ranking_score=ranking_score,
        raw_ranking_score=ranking_score + 2.0,
        grade="A" if ranking_score >= 90 else "B+",
        tier="TIER_1" if ranking_score >= 90 else "TIER_2",
        action=(
            "LIVE_CANDIDATE"
            if allowed
            else "REJECT"
        ),
        selected=selected,
        allowed=allowed,
        primary_reason="Test ranked opportunity",
        diversification_reason="Test diversification",
        rejection_reasons=[] if allowed else [
            "OPPORTUNITY_NOT_ALLOWED"
        ],
        warnings=[],
        strengths=["Strategy Score"],
        weaknesses=[],
    )


def build_ranked_opportunities():
    return [
        ranked_opportunity(
            rank=1,
            symbol="AAPL",
            strategy="BULL_PUT_SPREAD",
            direction="CALL",
            ranking_score=92.0,
            capital_required=1000.0,
            maximum_loss=1000.0,
            expected_profit=300.0,
            sector="TECHNOLOGY",
            correlation_group="MEGA_CAP_TECH",
            delta=18.0,
            theta=6.0,
            vega=-22.0,
        ),
        ranked_opportunity(
            rank=2,
            symbol="MSFT",
            strategy="BULL_CALL_SPREAD",
            direction="CALL",
            ranking_score=88.0,
            capital_required=1200.0,
            maximum_loss=1200.0,
            expected_profit=360.0,
            sector="TECHNOLOGY",
            correlation_group="MEGA_CAP_TECH",
            delta=20.0,
            theta=-4.0,
            vega=18.0,
        ),
        ranked_opportunity(
            rank=3,
            symbol="JPM",
            strategy="BEAR_CALL_SPREAD",
            direction="PUT",
            ranking_score=84.0,
            capital_required=900.0,
            maximum_loss=900.0,
            expected_profit=225.0,
            sector="FINANCIALS",
            correlation_group="BANKS",
            delta=-16.0,
            theta=5.0,
            vega=-15.0,
        ),
        ranked_opportunity(
            rank=4,
            symbol="XOM",
            strategy="BULL_CALL_SPREAD",
            direction="CALL",
            ranking_score=80.0,
            capital_required=800.0,
            maximum_loss=800.0,
            expected_profit=160.0,
            sector="ENERGY",
            correlation_group="ENERGY",
            delta=14.0,
            theta=-3.0,
            vega=12.0,
        ),
        ranked_opportunity(
            rank=5,
            symbol="AAPL",
            strategy="LONG_CALL",
            direction="CALL",
            ranking_score=78.0,
            capital_required=1000.0,
            maximum_loss=1000.0,
            expected_profit=200.0,
            sector="TECHNOLOGY",
            correlation_group="MEGA_CAP_TECH",
            delta=50.0,
            theta=-10.0,
            vega=30.0,
        ),
        ranked_opportunity(
            rank=6,
            symbol="ILLQ",
            strategy="LONG_CALL",
            direction="CALL",
            ranking_score=90.0,
            capital_required=500.0,
            maximum_loss=500.0,
            expected_profit=250.0,
            sector="UNKNOWN",
            correlation_group="",
            delta=45.0,
            theta=-8.0,
            vega=25.0,
            selected=False,
            allowed=False,
            readiness="REJECTED",
        ),
    ]


def print_result(result):
    print(
        "\n========== Portfolio Construction =========="
    )

    print(f"Valid                   : {result.valid}")
    print(f"Readiness               : {result.readiness}")
    print(f"Portfolio Score         : {result.portfolio_score:.2f}")
    print(f"Risk Score              : {result.risk_score:.2f}")
    print(f"Diversification Score   : {result.diversification_score:.2f}")
    print(f"Capital Efficiency      : {result.capital_efficiency_score:.2f}")

    print("\nAccepted Positions:")

    for index, position in enumerate(
        result.positions,
        start=1,
    ):
        print(
            f"{index}. "
            f"{position.symbol:<6} "
            f"{position.strategy:<22} "
            f"Contracts={position.contracts:<3} "
            f"Capital=${position.capital_required:>8.2f} "
            f"Risk=${position.maximum_loss:>8.2f} "
            f"Expected=${position.expected_profit:>8.2f} "
            f"Delta={position.delta:>7.2f} "
            f"Theta={position.theta:>7.2f} "
            f"Vega={position.vega:>7.2f}"
        )

    print("\nRejected Candidates:")

    for rejection in result.rejected:
        print(
            f"{rejection.symbol:<6} "
            f"{rejection.strategy:<22} "
            f"Score={rejection.ranking_score:>6.2f} "
            f"Reasons={', '.join(rejection.reasons)}"
        )

    exposure = result.exposure

    print("\nPortfolio Exposure:")

    print(
        f"Initial Capital         : "
        f"${exposure.initial_capital:,.2f}"
    )

    print(
        f"Capital Allocated       : "
        f"${exposure.total_capital_allocated:,.2f}"
    )

    print(
        f"Maximum Loss            : "
        f"${exposure.total_maximum_loss:,.2f}"
    )

    print(
        f"Expected Profit         : "
        f"${exposure.total_expected_profit:,.2f}"
    )

    print(
        f"Exposure %              : "
        f"{exposure.exposure_pct:.2%}"
    )

    print(
        f"Risk %                  : "
        f"{exposure.risk_pct:.2%}"
    )

    print(
        f"Expected Portfolio Ret. : "
        f"{exposure.expected_return_on_capital_pct:.2%}"
    )

    print(
        f"Reserve Cash            : "
        f"${exposure.reserve_cash:,.2f}"
    )

    print(
        f"Available Capital       : "
        f"${exposure.available_capital:,.2f}"
    )

    print("\nPortfolio Greeks:")

    print(f"Net Delta               : {exposure.net_delta:.4f}")
    print(f"Net Gamma               : {exposure.net_gamma:.5f}")
    print(f"Net Theta               : {exposure.net_theta:.4f}")
    print(f"Net Vega                : {exposure.net_vega:.4f}")
    print(f"Net Rho                 : {exposure.net_rho:.4f}")

    print("\nConcentration:")

    print(
        f"Symbol Exposure         : "
        f"{exposure.symbol_exposure}"
    )

    print(
        f"Sector Exposure         : "
        f"{exposure.sector_exposure}"
    )

    print(
        f"Direction Exposure      : "
        f"{exposure.direction_exposure}"
    )

    print(
        f"Correlation Exposure    : "
        f"{exposure.correlation_group_exposure}"
    )

    warnings = (
        ", ".join(result.warnings)
        if result.warnings
        else "-"
    )

    recommendations = (
        " | ".join(result.recommendations)
        if result.recommendations
        else "-"
    )

    print(f"\nWarnings                : {warnings}")
    print(f"Recommendations          : {recommendations}")


def main():
    limits = PortfolioRiskLimits(
        initial_capital=100000.0,

        maximum_portfolio_exposure_pct=0.40,
        maximum_total_risk_pct=0.15,

        maximum_position_pct=0.08,
        maximum_risk_per_trade_pct=0.025,

        reserve_cash_pct=0.20,

        maximum_positions=5,

        maximum_positions_per_symbol=1,
        maximum_positions_per_sector=2,
        maximum_positions_per_strategy=2,
        maximum_positions_per_direction=3,
        maximum_positions_per_correlation_group=2,

        maximum_symbol_exposure_pct=0.10,
        maximum_sector_exposure_pct=0.25,
        maximum_strategy_exposure_pct=0.25,
        maximum_direction_exposure_pct=0.35,
        maximum_correlation_group_exposure_pct=0.20,

        maximum_absolute_delta=250.0,
        maximum_absolute_gamma=10.0,
        maximum_absolute_theta=200.0,
        maximum_absolute_vega=500.0,

        minimum_ranking_score=60.0,
        minimum_strategy_score=65.0,
        minimum_portfolio_fit_score=40.0,
    )

    service = PortfolioService(
        limits=limits
    )

    ranked = build_ranked_opportunities()

    result = service.construct(
        ranked
    )

    print_result(result)

    # ---------------------------------------------
    # Focused assertions
    # ---------------------------------------------

    assert result.positions
    assert result.valid is True

    accepted_symbols = [
        position.symbol
        for position in result.positions
    ]

    # Duplicate AAPL position must not be accepted.
    assert accepted_symbols.count("AAPL") <= 1

    # Disallowed opportunity must not enter portfolio.
    assert "ILLQ" not in accepted_symbols

    assert (
        result.exposure.total_capital_allocated
        <= limits.maximum_portfolio_exposure_dollars
        + 0.01
    )

    assert (
        result.exposure.total_maximum_loss
        <= limits.maximum_total_risk_dollars
        + 0.01
    )

    assert (
        abs(result.exposure.net_delta)
        <= limits.maximum_absolute_delta
    )

    assert (
        abs(result.exposure.net_vega)
        <= limits.maximum_absolute_vega
    )

    assert (
        result.exposure.position_count
        <= limits.maximum_positions
    )

    duplicate_aapl_rejection = next(
        (
            rejection
            for rejection in result.rejected
            if (
                rejection.symbol == "AAPL"
                and rejection.strategy == "LONG_CALL"
            )
        ),
        None,
    )

    assert duplicate_aapl_rejection is not None

    assert (
        "MAXIMUM_POSITIONS_PER_SYMBOL_EXCEEDED"
        in duplicate_aapl_rejection.reasons
    )

    print(
        "\nAll portfolio-construction assertions passed."
    )

    print(
        "================================================"
    )


if __name__ == "__main__":
    main()
