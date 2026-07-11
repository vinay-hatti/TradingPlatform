from types import SimpleNamespace

from trading_ai.strategy_engine.institutional_opportunity import (
    InstitutionalOpportunity,
)
from trading_ai.strategy_engine.institutional_ranking_engine import (
    InstitutionalRankingEngine,
)
from trading_ai.strategy_engine.institutional_ranking_policy import (
    InstitutionalRankingPolicy,
)
from trading_ai.strategy_engine.opportunity_factory import (
    OpportunityFactory,
)


def opportunity(
    symbol,
    strategy,
    direction,
    strategy_score,
    expected_return_pct,
    probability_of_profit,
    liquidity_score,
    execution_score,
    confidence,
    portfolio_fit,
    readiness="LIVE_CANDIDATE",
    allowed=True,
    sector="TECHNOLOGY",
    correlation_group="MEGA_CAP_TECH",
    expected_profit=500.0,
    maximum_loss=1000.0,
    capital_required=1000.0,
    risk_profile="DEFINED_RISK",
    complexity="MULTI_LEG",
):
    return InstitutionalOpportunity(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        market_regime=(
            "BULL_TREND"
            if direction == "CALL"
            else "BEAR_TREND"
        ),
        strategy_score=strategy_score,
        allowed=allowed,
        readiness=readiness,
        recommendation=(
            "LIVE_CANDIDATE"
            if readiness == "LIVE_CANDIDATE"
            else "PAPER_TRADE_CANDIDATE"
        ),
        expected_return_pct=expected_return_pct,
        expected_profit=expected_profit,
        maximum_loss=maximum_loss,
        capital_required=capital_required,
        probability_of_profit=probability_of_profit,
        liquidity_score=liquidity_score,
        execution_score=execution_score,
        greeks_score=82.0,
        expected_move_score=84.0,
        data_confidence_score=confidence,
        risk_reward_score=80.0,
        portfolio_fit_score=portfolio_fit,
        strike=100.0,
        expiry="2026-08-21",
        dte=30,
        premium_type="CREDIT",
        risk_profile=risk_profile,
        complexity=complexity,
        sector=sector,
        correlation_group=correlation_group,
        contracts=1,
        rank_eligible=allowed,
    )


def build_opportunities():
    return [
        opportunity(
            symbol="AAPL",
            strategy="BULL_PUT_SPREAD",
            direction="CALL",
            strategy_score=92.0,
            expected_return_pct=0.24,
            probability_of_profit=0.72,
            liquidity_score=94.0,
            execution_score=91.0,
            confidence=88.0,
            portfolio_fit=84.0,
        ),
        opportunity(
            symbol="MSFT",
            strategy="BULL_PUT_SPREAD",
            direction="CALL",
            strategy_score=89.0,
            expected_return_pct=0.20,
            probability_of_profit=0.70,
            liquidity_score=92.0,
            execution_score=89.0,
            confidence=86.0,
            portfolio_fit=80.0,
        ),
        opportunity(
            symbol="NVDA",
            strategy="BULL_CALL_SPREAD",
            direction="CALL",
            strategy_score=91.0,
            expected_return_pct=0.35,
            probability_of_profit=0.61,
            liquidity_score=90.0,
            execution_score=87.0,
            confidence=82.0,
            portfolio_fit=76.0,
        ),
        opportunity(
            symbol="JPM",
            strategy="BEAR_CALL_SPREAD",
            direction="PUT",
            strategy_score=84.0,
            expected_return_pct=0.18,
            probability_of_profit=0.68,
            liquidity_score=85.0,
            execution_score=82.0,
            confidence=80.0,
            portfolio_fit=88.0,
            sector="FINANCIALS",
            correlation_group="BANKS",
        ),
        opportunity(
            symbol="XOM",
            strategy="BULL_CALL_SPREAD",
            direction="CALL",
            strategy_score=80.0,
            expected_return_pct=0.16,
            probability_of_profit=0.59,
            liquidity_score=81.0,
            execution_score=78.0,
            confidence=75.0,
            portfolio_fit=90.0,
            sector="ENERGY",
            correlation_group="ENERGY",
        ),
        opportunity(
            symbol="AAPL",
            strategy="LONG_CALL",
            direction="CALL",
            strategy_score=86.0,
            expected_return_pct=0.30,
            probability_of_profit=0.55,
            liquidity_score=90.0,
            execution_score=87.0,
            confidence=85.0,
            portfolio_fit=70.0,
            complexity="STANDARD",
        ),
        opportunity(
            symbol="ILLQ",
            strategy="LONG_CALL",
            direction="CALL",
            strategy_score=95.0,
            expected_return_pct=0.50,
            probability_of_profit=0.60,
            liquidity_score=25.0,
            execution_score=20.0,
            confidence=80.0,
            portfolio_fit=80.0,
            allowed=False,
            sector="UNKNOWN",
            correlation_group="",
            complexity="STANDARD",
        ),
        opportunity(
            symbol="RISK",
            strategy="SHORT_CALL",
            direction="PUT",
            strategy_score=90.0,
            expected_return_pct=0.25,
            probability_of_profit=0.75,
            liquidity_score=88.0,
            execution_score=84.0,
            confidence=82.0,
            portfolio_fit=70.0,
            risk_profile="UNDEFINED_RISK",
            complexity="STANDARD",
        ),
    ]


def print_ranked(item):
    opportunity = item.opportunity

    rejections = (
        ", ".join(item.rejection_reasons)
        if item.rejection_reasons
        else "-"
    )

    strengths = (
        ", ".join(item.strengths)
        if item.strengths
        else "-"
    )

    weaknesses = (
        ", ".join(item.weaknesses)
        if item.weaknesses
        else "-"
    )

    warnings = (
        ", ".join(item.warnings)
        if item.warnings
        else "-"
    )

    print(
        f"{item.rank:>2}. "
        f"{opportunity.symbol:<6} "
        f"{opportunity.strategy:<22} "
        f"RankScore={item.ranking_score:>6.2f} "
        f"Raw={item.raw_ranking_score:>6.2f} "
        f"Grade={item.grade:<3} "
        f"Tier={item.tier:<9} "
        f"Action={item.action:<24} "
        f"Selected={str(item.selected):<5} "
        f"Allowed={str(item.allowed):<5}"
    )

    print(f"    Reason        : {item.primary_reason}")
    print(f"    Diversification: {item.diversification_reason}")
    print(f"    Strengths     : {strengths}")
    print(f"    Weaknesses    : {weaknesses}")
    print(f"    Warnings      : {warnings}")
    print(f"    Rejections    : {rejections}")


def test_factory():
    factory = OpportunityFactory()

    scoring_result = SimpleNamespace(
        strategy="BULL_PUT_SPREAD",
        direction="CALL",
        market_regime="BULL_TREND",
        composite_score=88.0,
        allowed=True,
        readiness="LIVE_CANDIDATE",
        recommendation="LIVE_CANDIDATE",
        rejection_reasons=[],
        warnings=[],
        metadata={
            "premium_type": "CREDIT",
            "risk_profile": "DEFINED_RISK",
            "complexity": "MULTI_LEG",
        },
        breakdown=SimpleNamespace(
            liquidity_score=90.0,
            execution_score=86.0,
            greeks_score=82.0,
            expected_move_score=84.0,
            data_confidence_score=83.0,
            risk_reward_score=80.0,
        ),
    )

    strategy_candidate = SimpleNamespace(
        strategy="BULL_PUT_SPREAD",
        direction="CALL",
        premium_type="CREDIT",
        risk_profile="DEFINED_RISK",
        expected_move_score=84.0,
    )

    strike_candidate = SimpleNamespace(
        short_strike=100.0,
        long_strike=95.0,
        expiry="2026-08-21",
        dte=30,
        max_profit=250.0,
        max_loss=250.0,
        capital_required=250.0,
        probability_of_profit=0.70,
        allowed=True,
    )

    expiration_candidate = SimpleNamespace(
        expiry="2026-08-21",
        dte=30,
        allowed=True,
    )

    liquidity_profile = SimpleNamespace(
        liquidity_score=90.0,
        execution_score=86.0,
        allowed=True,
    )

    created = factory.create(
        symbol="AAPL",
        strategy_scoring_result=scoring_result,
        strategy_candidate=strategy_candidate,
        strike_candidate=strike_candidate,
        expiration_candidate=expiration_candidate,
        liquidity_profile=liquidity_profile,
        expected_return_pct=0.25,
        sector="TECHNOLOGY",
        correlation_group="MEGA_CAP_TECH",
    )

    assert created.symbol == "AAPL"
    assert created.strategy == "BULL_PUT_SPREAD"
    assert created.short_strike == 100.0
    assert created.long_strike == 95.0
    assert created.probability_of_profit == 0.70
    assert created.rank_eligible is True

    print("\nOpportunityFactory assertions passed.")


def main():
    policy = InstitutionalRankingPolicy(
        shortlist_size=5,
        live_shortlist_size=3,
        maximum_opportunities_per_symbol=1,
        maximum_opportunities_per_sector=2,
        maximum_same_direction=3,
        maximum_same_strategy=2,
        maximum_same_correlation_group=2,
    )

    engine = InstitutionalRankingEngine(
        policy=policy
    )

    opportunities = build_opportunities()

    print(
        "\n========== Institutional Ranking Engine =========="
    )

    ranked = engine.rank(
        opportunities=opportunities,
        shortlist_size=5,
        include_rejected=True,
    )

    for item in ranked:
        print_ranked(item)

    print("\n========== Selected Shortlist ==========")

    shortlist = [
        item
        for item in ranked
        if item.selected
    ]

    for item in shortlist:
        print(
            f"#{item.rank} "
            f"{item.opportunity.symbol} "
            f"{item.opportunity.strategy} "
            f"Score={item.ranking_score:.2f} "
            f"Action={item.action}"
        )

    print("\n========== Live Candidates ==========")

    live = engine.live_candidates(
        opportunities=opportunities,
        size=3,
    )

    if live:
        for item in live:
            print(
                f"#{item.rank} "
                f"{item.opportunity.symbol} "
                f"{item.opportunity.strategy} "
                f"Score={item.ranking_score:.2f}"
            )
    else:
        print("No live candidates.")

    print("\n========== Ranking Summary ==========")

    summary = engine.summary(ranked)

    for key, value in summary.items():
        print(f"{key:<28}: {value}")

    best = engine.best(
        opportunities=opportunities,
        allowed_only=True,
    )

    print("\n========== Best Opportunity ==========")

    if best:
        print(f"Symbol         : {best.opportunity.symbol}")
        print(f"Strategy       : {best.opportunity.strategy}")
        print(f"Ranking Score  : {best.ranking_score:.2f}")
        print(f"Grade          : {best.grade}")
        print(f"Tier           : {best.tier}")
        print(f"Action         : {best.action}")
    else:
        print("No allowed opportunity found.")

    # -------------------------------------------------
    # Focused assertions
    # -------------------------------------------------

    assert ranked
    assert ranked[0].allowed is True

    rejected_illiquid = next(
        item
        for item in ranked
        if item.opportunity.symbol == "ILLQ"
    )

    assert rejected_illiquid.allowed is False
    assert (
        "LIQUIDITY_SCORE_BELOW_MINIMUM"
        in rejected_illiquid.rejection_reasons
    )

    rejected_undefined_risk = next(
        item
        for item in ranked
        if item.opportunity.symbol == "RISK"
    )

    assert rejected_undefined_risk.allowed is False
    assert (
        "UNDEFINED_RISK_NOT_ALLOWED"
        in rejected_undefined_risk.rejection_reasons
    )

    selected_symbols = [
        item.opportunity.symbol
        for item in shortlist
    ]

    assert selected_symbols.count("AAPL") <= 1

    assert best is not None
    assert best.allowed is True
    assert best.ranking_score >= policy.minimum_ranking_score

    assert summary["total_opportunities"] == len(
        opportunities
    )

    assert summary["selected_opportunities"] <= 5

    test_factory()

    print("\nAll institutional-ranking assertions passed.")
    print("==================================================")


if __name__ == "__main__":
    main()
