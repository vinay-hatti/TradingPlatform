from trading_ai.trend_intelligence.platform_integration import TrendPlatformIntegrationService, TrendPlatformPolicy


def main():
    assert TrendPlatformIntegrationService._clip(4,2)==2
    assert TrendPlatformIntegrationService._clip(-4,2)==-2
    p=TrendPlatformPolicy()
    assert p.forecast_horizon_days==10
    assert p.scanner_adjustment_cap==2.0
    print("All Trend Platform Integration assertions passed.")
if __name__=="__main__": main()
