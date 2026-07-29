from pathlib import Path

def main():
    value=Path("scripts/run_market_ingestion.py").read_text()
    for token in ("--skip-trend-intelligence","_run_trend_intelligence_pipeline","trend_platform_integration"):
        assert token in value, token
    print("All Trend Market Ingestion contract assertions passed.")
if __name__=="__main__": main()
