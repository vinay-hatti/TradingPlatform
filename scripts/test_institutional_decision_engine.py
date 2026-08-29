from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from trading_ai.strategy_engine.decision_policy import (
    DecisionPolicy,
)
from trading_ai.strategy_engine.decision_request import (
    DecisionRequest,
)
from trading_ai.strategy_engine.institutional_decision_engine import (
    InstitutionalDecisionEngine,
)
from trading_ai.strategy_engine.institutional_decision_service import (
    InstitutionalDecisionService,
)
from trading_ai.strategy_engine.decision_serialization import (
    decision_run_to_dict,
)
from trading_ai.strategy_engine.portfolio_risk_limits import (
    PortfolioRiskLimits,
)


class FakeVolatilityEngine:
    def analyze(
        self,
        symbol,
        price_history,
        option_history=None,
    ):
        return SimpleNamespace(
            symbol=symbol,
            hv20=0.22,
            hv30=0.24,
            hv60=0.25,
            hv90=0.26,
            current_iv=0.36,
            iv_rank=72.0,
            iv_percentile=78.0,
            iv_hv_ratio=1.50,
            volatility_regime="HIGH_VOL",
            volatility_signal=(
                "VOL_COMPRESSION_CANDIDATE"
            ),
            confidence=85.0,
        )


class FakeExpectedMoveEngine:
    def analyze_from_option_chain(
        self,
        symbol,
        underlying_price,
        horizon_days,
        option_chain,
        implied_volatility=0.0,
        historical_volatility=0.0,
        atr=0.0,
        target_expiry=None,
    ):
        move = underlying_price * 0.08

        return SimpleNamespace(
            symbol=symbol,
            horizon_days=horizon_days,
            blended_move=move,
            blended_move_pct=8.0,
            lower_bound=(
                underlying_price - move
            ),
            upper_bound=(
                underlying_price + move
            ),
            confidence_score=84.0,
            source_agreement_score=82.0,
            move_regime="NORMAL_MOVE",
            expansion_signal=(
                "IMPLIED_MOVE_OVERPRICED"
            ),
        )


class FakeStrategySelector:
    def select(
        self,
        symbol,
        direction,
        market_regime,
        volatility_profile,
        expected_move_profile=None,
    ):
        return [
            SimpleNamespace(
                symbol=symbol,
                strategy=(
                    "BULL_PUT_SPREAD"
                    if direction == "CALL"
                    else "BEAR_CALL_SPREAD"
                ),
                direction=direction,
                score=90.0,
                expected_move_score=86.0,
                allowed=True,
                risk_profile="DEFINED_RISK",
                premium_type="CREDIT",
                confidence=85.0,
                warnings=[],
            )
        ]


class FakeExpirationOptimizer:
    def optimize(
        self,
        symbol,
        strategy,
        underlying_price,
        option_chain,
        volatility_profile=None,
        top_n=5,
    ):
        return [
            SimpleNamespace(
                symbol=symbol,
                strategy=strategy,
                expiry="2026-08-21",
                dte=30,
                composite_score=88.0,
                allowed=True,
                warnings=[],
            )
        ][:top_n]


class FakeStrikeOptimizer:
    def optimize(
        self,
        symbol,
        strategy,
        underlying_price,
        option_chain,
        top_n=5,
    ):
        if strategy == "BULL_PUT_SPREAD":
            short_strike = (
                underlying_price * 0.95
            )
            long_strike = (
                underlying_price * 0.90
            )
            net_delta = 0.20
        else:
            short_strike = (
                underlying_price * 1.05
            )
            long_strike = (
                underlying_price * 1.10
            )
            net_delta = -0.20

        candidate = SimpleNamespace(
            symbol=symbol,
            strategy=strategy,
            short_strike=round(
                short_strike,
                2,
            ),
            long_strike=round(
                long_strike,
                2,
            ),
            expiry="2026-08-21",
            dte=30,
            credit_or_debit=2.00,
            width=5.00,
            max_profit=200.0,
            max_loss=300.0,
            short_delta=0.30,
            long_delta=0.10,
            net_delta=net_delta,
            net_gamma=0.01,
            net_theta=0.05,
            net_vega=-0.20,
            net_rho=0.01,
            liquidity_score=90.0,
            execution_score=86.0,
            greek_score=84.0,
            risk_reward_score=75.0,
            composite_score=88.0,
            institutional_composite_score=89.0,
            allowed=True,
            warnings=[],
            probability_of_profit=0.70,
        )

        return [
            candidate
        ][:top_n]


class FakeGreeksOptimizer:
    pass


class FakeLiquidityEngine:
    pass


class FakeMultiStrategyService:
    pass


def build_prices(
    start_price,
):
    rows = []

    price = float(
        start_price
    )

    for index in range(120):
        price *= (
            1.002
            if index % 2 == 0
            else 0.999
        )

        rows.append({
            "date": (
                pd.Timestamp("2026-01-01")
                + pd.Timedelta(
                    days=index
                )
            ),
            "close": price,
        })

    return pd.DataFrame(
        rows
    )


def build_chain(
    underlying,
):
    rows = []

    for strike_multiplier in [
        0.90,
        0.95,
        1.00,
        1.05,
        1.10,
    ]:
        strike = round(
            underlying
            * strike_multiplier,
            2,
        )

        for option_type in [
            "CALL",
            "PUT",
        ]:
            rows.append({
                "option_symbol": (
                    f"TEST{option_type[0]}"
                    f"{strike}"
                ),
                "option_type":
                    option_type,
                "strike": strike,
                "expiry":
                    "2026-08-21",
                "dte": 30,
                "bid": 4.90,
                "ask": 5.10,
                "mid": 5.00,
                "last": 5.00,
                "volume": 1000,
                "open_interest": 4000,
                "bid_size": 25,
                "ask_size": 25,
                "implied_volatility":
                    0.36,
                "delta": (
                    0.50
                    if option_type == "CALL"
                    else -0.50
                ),
                "gamma": 0.04,
                "theta": -0.05,
                "vega": 0.30,
                "rho": 0.05,
            })

    return pd.DataFrame(
        rows
    )


def print_decision(
    decision,
):
    print(
        f"\nDecision: "
        f"{decision.symbol} "
        f"{decision.strategy}"
    )

    print(
        f"Decision ID       : "
        f"{decision.decision_id}"
    )

    print(
        f"Action            : "
        f"{decision.action}"
    )

    print(
        f"Readiness         : "
        f"{decision.readiness}"
    )

    print(
        f"Allowed           : "
        f"{decision.allowed}"
    )

    print(
        f"Selected          : "
        f"{decision.selected}"
    )

    print(
        f"Rank              : "
        f"{decision.rank}"
    )

    print(
        f"Ranking Score     : "
        f"{decision.ranking_score:.2f}"
    )

    print(
        f"Strategy Score    : "
        f"{decision.strategy_score:.2f}"
    )

    print(
        f"Underlying        : "
        f"${decision.underlying_price:.2f}"
    )

    print(
        f"Expiration        : "
        f"{decision.expiry}"
    )

    print(
        f"Short Strike      : "
        f"{decision.short_strike}"
    )

    print(
        f"Long Strike       : "
        f"{decision.long_strike}"
    )

    print(
        f"Contracts         : "
        f"{decision.contracts}"
    )

    print(
        f"Capital Required  : "
        f"${decision.capital_required:.2f}"
    )

    print(
        f"Maximum Loss      : "
        f"${decision.maximum_loss:.2f}"
    )

    print(
        f"Expected Profit   : "
        f"${decision.expected_profit:.2f}"
    )

    print(
        f"Expected Return   : "
        f"{decision.expected_return_pct:.2%}"
    )

    pop = (
        f"{decision.probability_of_profit:.2%}"
        if decision.probability_of_profit
        is not None
        else "N/A"
    )

    print(
        f"Probability       : "
        f"{pop}"
    )

    print(
        f"Expected Move     : "
        f"${decision.expected_move:.2f}"
    )

    print(
        f"Expected Range    : "
        f"${decision.expected_range_low:.2f} - "
        f"${decision.expected_range_high:.2f}"
    )

    print(
        f"Liquidity Score   : "
        f"{decision.liquidity_score:.2f}"
    )

    print(
        f"Execution Score   : "
        f"{decision.execution_score:.2f}"
    )

    print(
        f"Greeks Score      : "
        f"{decision.greeks_score:.2f}"
    )

    print(
        f"Net Delta         : "
        f"{decision.net_delta:.4f}"
    )

    print(
        f"Net Theta         : "
        f"{decision.net_theta:.4f}"
    )

    print(
        f"Net Vega          : "
        f"{decision.net_vega:.4f}"
    )

    rejections = (
        ", ".join(
            decision.rejection_reasons
        )
        if decision.rejection_reasons
        else "-"
    )

    warnings = (
        ", ".join(
            decision.warnings
        )
        if decision.warnings
        else "-"
    )

    print(
        f"Risk Surface Score : "
        f"{decision.risk_surface_score:.2f}"
    )

    print(
        f"Risk Surface Grade : "
        f"{decision.risk_surface_grade}"
    )

    print(
        f"Surface Severity   : "
        f"{decision.risk_surface_severity}"
    )

    print(
        f"Surface Worst PnL  : "
        f"${decision.risk_surface_worst_case_pnl:,.2f}"
    )

    print(
        f"Rejections        : "
        f"{rejections}"
    )

    print(
        f"Warnings          : "
        f"{warnings}"
    )


def main():
    symbols = [
        "AAPL",
        "MSFT",
        "JPM",
    ]

    prices = {
        "AAPL": build_prices(
            200.0
        ),
        "MSFT": build_prices(
            450.0
        ),
        "JPM": build_prices(
            220.0
        ),
    }

    chains = {
        "AAPL": build_chain(
            200.0
        ),
        "MSFT": build_chain(
            450.0
        ),
        "JPM": build_chain(
            220.0
        ),
    }

    request = DecisionRequest(
        symbols=symbols,
        price_history_by_symbol=prices,
        option_chain_by_symbol=chains,
        signal_by_symbol={
            "AAPL": "CALL",
            "MSFT": "CALL",
            "JPM": "PUT",
        },
        market_regime_by_symbol={
            "AAPL": "BULL_TREND",
            "MSFT": "BULL_TREND",
            "JPM": "BEAR_TREND",
        },
        technical_score_by_symbol={
            "AAPL": 90.0,
            "MSFT": 87.0,
            "JPM": 84.0,
        },
        underlying_price_by_symbol={
            "AAPL": 200.0,
            "MSFT": 450.0,
            "JPM": 220.0,
        },
        atr_by_symbol={
            "AAPL": 5.0,
            "MSFT": 8.0,
            "JPM": 4.0,
        },
        sector_by_symbol={
            "AAPL": "TECHNOLOGY",
            "MSFT": "TECHNOLOGY",
            "JPM": "FINANCIALS",
        },
        industry_by_symbol={
            "AAPL": "CONSUMER_ELECTRONICS",
            "MSFT": "SOFTWARE",
            "JPM": "BANKS",
        },
        correlation_group_by_symbol={
            "AAPL": "MEGA_CAP_TECH",
            "MSFT": "MEGA_CAP_TECH",
            "JPM": "BANKS",
        },
        portfolio_fit_by_symbol={
            "AAPL": 85.0,
            "MSFT": 80.0,
            "JPM": 88.0,
        },
        strategy_limit_per_symbol=1,
        expiration_limit_per_strategy=1,
        strike_limit_per_expiration=1,
        target_dte=30,
        initial_capital=100000.0,
        construct_portfolio=True,
        include_rejected=True,
    )

    policy = DecisionPolicy(
        minimum_technical_score=50.0,
        minimum_strategy_score=60.0,
        minimum_ranking_score=55.0,
        minimum_liquidity_score=50.0,
        minimum_execution_score=45.0,
        minimum_greeks_score=50.0,
        reject_missing_maximum_loss=True,
    )

    portfolio_limits = PortfolioRiskLimits(
        initial_capital=100000.0,
        maximum_portfolio_exposure_pct=0.30,
        maximum_total_risk_pct=0.12,
        maximum_position_pct=0.05,
        maximum_risk_per_trade_pct=0.02,
        reserve_cash_pct=0.30,
        maximum_positions=5,
        maximum_positions_per_symbol=1,
        maximum_positions_per_sector=2,
        maximum_positions_per_correlation_group=2,
        minimum_ranking_score=55.0,
        minimum_strategy_score=60.0,
        minimum_portfolio_fit_score=40.0,
    )

    engine = InstitutionalDecisionEngine(
        policy=policy,
        volatility_engine=(
            FakeVolatilityEngine()
        ),
        expected_move_engine=(
            FakeExpectedMoveEngine()
        ),
        strategy_selector=(
            FakeStrategySelector()
        ),
        expiration_optimizer=(
            FakeExpirationOptimizer()
        ),
        strike_optimizer=(
            FakeStrikeOptimizer()
        ),
        greeks_optimizer=(
            FakeGreeksOptimizer()
        ),
        liquidity_engine=(
            FakeLiquidityEngine()
        ),
        multi_strategy_service=(
            FakeMultiStrategyService()
        ),
        portfolio_limits=(
            portfolio_limits
        ),
    )

    assert_phase3_distribution_integration(engine)

    service = InstitutionalDecisionService(
        engine=engine
    )

    result, output_path = (
        service.run_and_export(
            request=request,
            output_file=(
                "reports/strategy_engine/"
                "institutional_decision_test.json"
            ),
        )
    )

    print(
        "\n========== Institutional Decision Engine =========="
    )

    print(
        f"Total Symbols       : "
        f"{result.total_symbols}"
    )

    print(
        f"Processed Symbols   : "
        f"{result.processed_symbols}"
    )

    print(
        f"Total Candidates    : "
        f"{result.total_candidates}"
    )

    print(
        f"Accepted Candidates : "
        f"{result.accepted_candidates}"
    )

    print(
        f"Rejected Candidates : "
        f"{result.rejected_candidates}"
    )

    print(
        f"Selected Decisions  : "
        f"{result.selected_count}"
    )

    print(
        f"Overall Readiness   : "
        f"{result.overall_readiness}"
    )

    print(
        f"Overall Action      : "
        f"{result.overall_action}"
    )

    print(
        f"Valid               : "
        f"{result.valid}"
    )

    print(
        f"Output              : "
        f"{output_path}"
    )

    for decision in result.decisions:
        print_decision(
            decision
        )

    if result.portfolio_result:
        portfolio = (
            result.portfolio_result
        )

        print(
            "\n========== Portfolio Result =========="
        )

        print(
            f"Valid             : "
            f"{portfolio.valid}"
        )

        print(
            f"Readiness         : "
            f"{portfolio.readiness}"
        )

        print(
            f"Portfolio Score   : "
            f"{portfolio.portfolio_score:.2f}"
        )

        print(
            f"Positions         : "
            f"{len(portfolio.positions)}"
        )

        print(
            f"Capital Allocated : "
            f"${portfolio.exposure.total_capital_allocated:,.2f}"
        )

        print(
            f"Maximum Loss      : "
            f"${portfolio.exposure.total_maximum_loss:,.2f}"
        )

        print(
            f"Expected Profit   : "
            f"${portfolio.exposure.total_expected_profit:,.2f}"
        )

    # -------------------------------------------------
    # Focused assertions
    # -------------------------------------------------

    assert result.valid is True
    assert result.total_symbols == 3
    assert result.processed_symbols == 3
    assert result.total_candidates == 3

    assert len(
        result.decisions
    ) == 3

    assert all(
        decision.strategy
        in {
            "BULL_PUT_SPREAD",
            "BEAR_CALL_SPREAD",
        }
        for decision in result.decisions
    )

    assert all(
        decision.maximum_loss > 0
        for decision in result.decisions
    )

    assert all(
        decision.expected_move > 0
        for decision in result.decisions
    )

    assert all(
        decision.liquidity_score > 0
        for decision in result.decisions
    )

    assert Path(
        output_path
    ).exists()

    if result.portfolio_result:
        assert (
            result
            .portfolio_result
            .exposure
            .total_capital_allocated
            <= portfolio_limits
            .maximum_portfolio_exposure_dollars
            + 0.01
        )

        assert (
            result
            .portfolio_result
            .exposure
            .total_maximum_loss
            <= portfolio_limits
            .maximum_total_risk_dollars
            + 0.01
        )

    # ---------------------------------------------
    # Phase 4 risk-surface integration assertions
    # ---------------------------------------------

    for bundle in result.candidate_bundles:
        assert bundle.risk_surface_profile is not None
        assert bundle.risk_surface_profile.valid is True
        assert bundle.risk_surface_profile.point_count > 0
        assert bundle.has_valid_risk_surface_profile is True

    for decision in result.decisions:
        assert decision.risk_surface_profile is not None
        assert decision.risk_surface_point_count > 0
        assert 0.0 <= decision.risk_surface_score <= 100.0
        assert decision.risk_surface_grade in {"A", "B", "C", "D", "F"}
        assert decision.risk_surface_severity in {
            "LOW", "MODERATE", "SEVERE", "CRITICAL"
        }
        assert isinstance(decision.risk_surface_allowed, bool)
        assert (
            decision.risk_surface_worst_case_pnl
            <= decision.risk_surface_best_case_pnl
        )

    serialized = decision_run_to_dict(result)
    serialized_decision = serialized["decisions"][0]
    assert "risk_surface_profile" in serialized_decision
    assert "risk_surface_score" in serialized_decision
    assert (
        serialized_decision["risk_surface_profile"]["point_count"]
        > 0
    )

    print(
        "\nAll institutional-decision assertions passed."
    )

    print(
        "=================================================="
    )


def assert_phase3_distribution_integration(engine):
    """Validate source precedence and account-capital propagation."""
    captured = {}

    class CapturingDistributionService:
        policy = SimpleNamespace(minimum_observations=30)

        def analyze_strategy(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                valid=True,
                allowed=True,
                observation_count=len(kwargs["pnl_values"]),
                historical_var=100.0,
                historical_expected_shortfall=125.0,
                parametric_var=95.0,
                parametric_expected_shortfall=120.0,
                historical_var_99=150.0,
                historical_expected_shortfall_99=175.0,
                downside_deviation=0.02,
                skewness=-0.25,
                excess_kurtosis=1.5,
                probability_of_large_loss=0.03,
                probability_of_severe_loss=0.01,
                probability_of_critical_loss=0.0,
                drawdown_at_risk=0.05,
                expected_drawdown_shortfall=0.07,
                ulcer_index=2.0,
                pain_index=1.0,
                omega_ratio=1.2,
                sortino_ratio=1.1,
                gain_to_pain_ratio=1.3,
                tail_risk_score=82.0,
                tail_risk_grade="B",
                risk_severity="LOW",
                rejection_reasons=[],
                warnings=[],
                metadata={},
            )

    original_service = engine.distribution_risk_service
    engine.distribution_risk_service = CapturingDistributionService()

    try:
        monte_carlo_values = [float(index - 50) for index in range(100)]
        scenario_points = [
            SimpleNamespace(stressed_pnl=-10.0),
            SimpleNamespace(stressed_pnl=5.0),
        ]

        profile = engine._distribution_risk_profile(
            symbol="AAPL",
            strategy_candidate=SimpleNamespace(strategy="BULL_PUT_SPREAD"),
            payoff_profile=SimpleNamespace(capital_required=2500.0),
            probability_profile=SimpleNamespace(
                metadata={"pnl_values": monte_carlo_values}
            ),
            scenario_profile=SimpleNamespace(
                scenario_points=scenario_points
            ),
            strike_candidate=SimpleNamespace(),
            initial_capital=100000.0,
        )

        assert profile.valid is True
        assert captured["pnl_values"] == monte_carlo_values
        assert captured["capital_required"] == 2500.0
        assert captured["initial_capital"] == 100000.0
        assert profile.metadata["distribution_source"] == (
            "PROBABILITY_MONTE_CARLO_PNL"
        )
        assert profile.metadata["scenario_observation_count"] == 2
        assert profile.metadata["monte_carlo_observation_count"] == 100
    finally:
        engine.distribution_risk_service = original_service


if __name__ == "__main__":
    main()
