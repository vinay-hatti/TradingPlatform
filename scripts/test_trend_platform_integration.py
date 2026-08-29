from trading_ai.trend_intelligence.platform_integration import TrendPlatformIntegrationService, TrendPlatformPolicy
from trading_ai.trend_intelligence.platform_adapters import TrendScannerAdapter, TrendDecisionAdapter, TrendPortfolioRiskAdapter, TrendMarketOverviewAdapter

def main():
    assert TrendPlatformIntegrationService._clip(4, 2) == 2
    assert TrendPlatformIntegrationService._clip(-4, 2) == -2
    policy = TrendPlatformPolicy()
    assert policy.forecast_horizon_days == 10
    assert policy.scanner_adjustment_cap == 2.0
    for cls in (TrendScannerAdapter, TrendDecisionAdapter, TrendPortfolioRiskAdapter, TrendMarketOverviewAdapter):
        assert cls is not None
    print("All Trend Platform Integration assertions passed.")

if __name__ == "__main__": main()
