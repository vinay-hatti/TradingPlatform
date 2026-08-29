import json
from types import SimpleNamespace

from trading_ai.strategy_engine.market_breadth_policy import MarketBreadthPolicy
from trading_ai.strategy_engine.market_breadth_service import MarketBreadthService
from trading_ai.strategy_engine.market_breadth_serialization import market_breadth_to_dict


def profile(symbol, regime, score=75.0, confidence=80.0):
    return SimpleNamespace(
        symbol=symbol, current_regime=regime, regime_score=score,
        confidence_score=confidence, valid=True,
    )


def main():
    service = MarketBreadthService()
    bullish = service.analyze_portfolio({
        "AAPL": profile("AAPL", "BULL_TREND", 82, 88),
        "MSFT": profile("MSFT", "STRONG_BULL_TREND", 86, 90),
        "JPM": profile("JPM", "RECOVERY", 72, 78),
        "XOM": profile("XOM", "RANGE_BOUND", 64, 70),
    })
    assert bullish.valid
    assert bullish.portfolio_regime == "BULL_TREND"
    assert bullish.bullish_breadth >= 0.75
    assert len(bullish.contributions) == 4
    assert bullish.effective_symbol_count > 3.0

    stressed = MarketBreadthService(MarketBreadthPolicy(reject_critical_market_state=True)).analyze_portfolio({
        "A": profile("A", "STRESS"),
        "B": profile("B", "STRESS"),
        "C": profile("C", "BEAR_TREND"),
        "D": profile("D", "RANGE_BOUND"),
    })
    assert stressed.portfolio_regime == "STRESS"
    assert stressed.breadth_severity == "CRITICAL"
    assert stressed.allowed is False
    assert "CRITICAL_MARKET_BREADTH_STATE" in stressed.rejection_reasons

    dispersed = service.analyze_portfolio([
        profile("A", "BULL_TREND"), profile("B", "BEAR_TREND"),
        profile("C", "RANGE_BOUND"), profile("D", "HIGH_VOLATILITY"),
    ])
    assert dispersed.regime_dispersion > 0.5
    assert "ELEVATED_MARKET_REGIME_DISPERSION" in dispersed.warnings

    invalid = service.analyze_portfolio([profile("A", "BULL_TREND")])
    assert invalid.valid is False
    assert "INSUFFICIENT_VALID_REGIME_PROFILES" in invalid.warnings

    payload = market_breadth_to_dict(bullish)
    json.dumps(payload)
    assert payload["portfolio_regime"] == "BULL_TREND"

    print("========== MARKET BREADTH ANALYTICS ==========")
    print(f"Portfolio Regime        : {bullish.portfolio_regime}")
    print(f"Bullish Breadth         : {bullish.bullish_breadth:.2%}")
    print(f"Regime Dispersion       : {bullish.regime_dispersion:.2%}")
    print(f"Effective Symbol Count  : {bullish.effective_symbol_count:.2f}")
    print(f"Breadth Score           : {bullish.breadth_score:.2f}")
    print("\nAll market-breadth assertions passed.")


if __name__ == "__main__":
    main()
