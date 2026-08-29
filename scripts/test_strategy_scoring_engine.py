from types import SimpleNamespace

from trading_ai.strategy_engine.strategy_scoring_context import (
    StrategyScoringContext,
)
from trading_ai.strategy_engine.strategy_scoring_engine import (
    StrategyScoringEngine,
)


def build_high_quality_context():
    return StrategyScoringContext(
        symbol="AAPL",
        strategy="BULL_PUT_SPREAD",
        direction="CALL",
        market_regime="BULL_TREND",

        technical_score=88.0,
        volatility_score=92.0,
        expected_move_score=86.0,
        strategy_selection_score=94.0,

        strike_score=89.0,
        expiration_score=87.0,
        greeks_score=84.0,

        liquidity_score=91.0,
        execution_score=88.0,

        risk_reward_score=82.0,
        data_confidence_score=85.0,
        portfolio_fit_score=78.0,

        strategy_allowed=True,
        strike_allowed=True,
        expiration_allowed=True,
        greeks_allowed=True,
        liquidity_allowed=True,

        risk_profile="DEFINED_RISK",
        premium_type="CREDIT",
        complexity="MULTI_LEG",
    )


def build_low_liquidity_context():
    return StrategyScoringContext(
        symbol="TEST",
        strategy="LONG_CALL",
        direction="CALL",
        market_regime="BULL_TREND",

        technical_score=92.0,
        volatility_score=80.0,
        expected_move_score=85.0,
        strategy_selection_score=88.0,

        strike_score=75.0,
        expiration_score=78.0,
        greeks_score=72.0,

        liquidity_score=30.0,
        execution_score=25.0,

        risk_reward_score=70.0,
        data_confidence_score=80.0,
        portfolio_fit_score=70.0,

        strategy_allowed=True,
        strike_allowed=True,
        expiration_allowed=True,
        greeks_allowed=True,
        liquidity_allowed=False,

        risk_profile="DEFINED_RISK",
        premium_type="DEBIT",
        complexity="STANDARD",
    )


def build_low_confidence_context():
    return StrategyScoringContext(
        symbol="SPARSE",
        strategy="LONG_PUT",
        direction="PUT",
        market_regime="BEAR_TREND",

        technical_score=80.0,
        volatility_score=65.0,
        expected_move_score=60.0,
        strategy_selection_score=82.0,

        strike_score=70.0,
        expiration_score=72.0,
        greeks_score=74.0,

        liquidity_score=68.0,
        execution_score=65.0,

        risk_reward_score=70.0,
        data_confidence_score=25.0,
        portfolio_fit_score=60.0,

        strategy_allowed=True,
        strike_allowed=True,
        expiration_allowed=True,
        greeks_allowed=True,
        liquidity_allowed=True,

        risk_profile="DEFINED_RISK",
        premium_type="DEBIT",
        complexity="STANDARD",
    )


def print_result(result):
    print(
        f"\n========== {result.symbol} "
        f"{result.strategy} =========="
    )

    print(f"Raw Score           : {result.raw_composite_score:.2f}")
    print(f"Penalty             : {result.total_penalty:.2f}")
    print(f"Final Score         : {result.composite_score:.2f}")
    print(f"Grade               : {result.grade}")
    print(f"Confidence          : {result.confidence_label}")
    print(f"Readiness           : {result.readiness}")
    print(f"Allowed             : {result.allowed}")
    print(f"Recommendation      : {result.recommendation}")
    print(f"Primary Reason      : {result.primary_reason}")

    rejection_reasons = (
        ", ".join(result.rejection_reasons)
        if result.rejection_reasons
        else "-"
    )

    strengths = (
        ", ".join(result.strengths)
        if result.strengths
        else "-"
    )

    weaknesses = (
        ", ".join(result.weaknesses)
        if result.weaknesses
        else "-"
    )

    warnings = (
        ", ".join(result.warnings)
        if result.warnings
        else "-"
    )

    print(f"Rejections          : {rejection_reasons}")
    print(f"Strengths           : {strengths}")
    print(f"Weaknesses          : {weaknesses}")
    print(f"Warnings            : {warnings}")

    b = result.breakdown

    print("\nScore Breakdown:")
    print(f"  Technical         : {b.technical_score:>6.2f}")
    print(f"  Volatility        : {b.volatility_score:>6.2f}")
    print(f"  Expected Move     : {b.expected_move_score:>6.2f}")
    print(f"  Strategy Select   : {b.strategy_selection_score:>6.2f}")
    print(f"  Strike            : {b.strike_score:>6.2f}")
    print(f"  Expiration        : {b.expiration_score:>6.2f}")
    print(f"  Greeks            : {b.greeks_score:>6.2f}")
    print(f"  Liquidity         : {b.liquidity_score:>6.2f}")
    print(f"  Execution         : {b.execution_score:>6.2f}")
    print(f"  Risk Reward       : {b.risk_reward_score:>6.2f}")
    print(f"  Data Confidence   : {b.data_confidence_score:>6.2f}")
    print(f"  Portfolio Fit     : {b.portfolio_fit_score:>6.2f}")


def test_build_context(engine):
    strategy_candidate = SimpleNamespace(
        strategy="BULL_PUT_SPREAD",
        direction="CALL",
        score=92.0,
        allowed=True,
        risk_profile="DEFINED_RISK",
        premium_type="CREDIT",
        expected_move_score=88.0,
    )

    strike_candidate = SimpleNamespace(
        institutional_composite_score=87.0,
        composite_score=84.0,
        risk_reward_score=80.0,
        allowed=True,
    )

    expiration_candidate = SimpleNamespace(
        composite_score=85.0,
        allowed=True,
    )

    greeks_profile = SimpleNamespace(
        composite_score=83.0,
        allowed=True,
    )

    liquidity_profile = SimpleNamespace(
        liquidity_score=90.0,
        execution_score=86.0,
        allowed=True,
    )

    expected_move_profile = SimpleNamespace(
        confidence_score=82.0,
        source_agreement_score=88.0,
    )

    volatility_profile = SimpleNamespace(
        confidence=84.0,
        iv_rank=78.0,
        volatility_regime="HIGH_VOL",
    )

    context = engine.build_context(
        symbol="AAPL",
        strategy_candidate=strategy_candidate,
        market_regime="BULL_TREND",
        technical_score=89.0,
        strike_candidate=strike_candidate,
        expiration_candidate=expiration_candidate,
        greeks_profile=greeks_profile,
        liquidity_profile=liquidity_profile,
        expected_move_profile=expected_move_profile,
        volatility_profile=volatility_profile,
        portfolio_fit_score=76.0,
    )

    result = engine.score(context)

    print_result(result)

    assert context.strategy == "BULL_PUT_SPREAD"
    assert context.liquidity_score == 90.0
    assert context.execution_score == 86.0
    assert context.greeks_score == 83.0
    assert result.composite_score > 0


def main():
    engine = StrategyScoringEngine()

    print(
        "\n========== Institutional Strategy "
        "Scoring Engine =========="
    )

    contexts = [
        build_high_quality_context(),
        build_low_liquidity_context(),
        build_low_confidence_context(),
    ]

    results = engine.rank(
        contexts=contexts,
        allowed_only=False,
    )

    for result in results:
        print_result(result)

    best = engine.best(
        contexts=contexts,
        allowed_only=True,
    )

    print("\n========== Best Allowed Strategy ==========")

    if best:
        print(f"Symbol         : {best.symbol}")
        print(f"Strategy       : {best.strategy}")
        print(f"Score          : {best.composite_score:.2f}")
        print(f"Grade          : {best.grade}")
        print(f"Readiness      : {best.readiness}")
        print(f"Recommendation : {best.recommendation}")
    else:
        print("No allowed strategy found.")

    print("\n========== Integrated Context Test ==========")

    test_build_context(engine)

    # -------------------------------------------------
    # Focused assertions
    # -------------------------------------------------

    high_quality = next(
        result
        for result in results
        if result.symbol == "AAPL"
    )

    low_liquidity = next(
        result
        for result in results
        if result.symbol == "TEST"
    )

    low_confidence = next(
        result
        for result in results
        if result.symbol == "SPARSE"
    )

    assert high_quality.allowed is True
    assert high_quality.composite_score >= 75.0

    assert low_liquidity.allowed is False
    assert "LIQUIDITY_NOT_ALLOWED" in low_liquidity.rejection_reasons
    assert "LIQUIDITY_SCORE_BELOW_MINIMUM" in (
        low_liquidity.rejection_reasons
    )

    assert low_confidence.total_penalty > 0
    assert "Low data confidence" in low_confidence.warnings

    assert best is not None
    assert best.symbol == "AAPL"

    print("\nAll strategy-scoring assertions passed.")
    print("=================================================")


if __name__ == "__main__":
    main()
