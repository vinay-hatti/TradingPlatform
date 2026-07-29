from pathlib import Path

def main():
    value = Path("scripts/run_market_ingestion.py").read_text()
    for token in (
        "--skip-trend-intelligence",
        "--force-trend-refresh",
        "_run_trend_intelligence_pipeline",
        "run_trend_intelligence.py",
        "run_trend_transition_intelligence.py",
        "run_trend_forecasting.py",
        "run_institutional_trend_intelligence.py",
        "run_trend_platform_integration.py",
        "trend_refreshed=trend_refreshed",
    ):
        assert token in value, token
    assert value.index("_run_trend_intelligence_pipeline(args, symbols)") < value.index("_run_market_overview(")
    print("All Trend Market Ingestion contract assertions passed.")

if __name__ == "__main__": main()
