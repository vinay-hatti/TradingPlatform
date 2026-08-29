from datetime import datetime, timezone
from trading_ai.scanner.universe_management import LiquidityGovernanceEngine, LiquidityGovernancePolicy, LiquidityMetrics


def main():
    engine = LiquidityGovernanceEngine(LiquidityGovernancePolicy())
    security = {"symbol": "GOOD", "exchange": "NASDAQ", "asset_type": "EQUITY", "options_eligible": "true"}
    good = LiquidityMetrics("GOOD", datetime.now(timezone.utc), 100.0, 1000000, 100000000.0, 0.01, 10000000000.0, 1000, 5000)
    result = engine.evaluate(security, good)
    assert result.eligible and result.status == "ELIGIBLE"
    bad = LiquidityMetrics("BAD", datetime.now(timezone.utc), 1.0, 100, 100.0, 0.50, 1000.0, 0, 0)
    result = engine.evaluate({**security, "symbol": "BAD"}, bad)
    assert not result.eligible and "PRICE_BELOW_MINIMUM" in result.rejection_reasons
    assert "SPREAD_ABOVE_MAXIMUM" in result.rejection_reasons
    print("M35 Phase 1 Step 4 liquidity governance assertions passed.")

if __name__ == "__main__": main()
