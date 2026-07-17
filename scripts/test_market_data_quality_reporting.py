import tempfile
from pathlib import Path
from trading_ai.market.market_data_quality_reporting import MarketDataQualityReport

def main():
    report = MarketDataQualityReport()
    pipeline={"state":"RUNNING","score":96,"received_count":10,"accepted_count":9,"rejected_count":1}
    feed={"provider":"paper","state":"HEALTHY","score":100,"recommendation":"CONTINUE"}
    reconciliation={"total_count":1,"matched_count":1,"rejected_count":0,"profiles":({"symbol":"AAPL","score":100,"recommendation":"ACCEPT"},)}
    assert "Normalized Market Data Pipeline" in report.pipeline_html(pipeline)
    assert "Feed Health and Recovery" in report.feed_html(feed)
    assert "Live/Historical Reconciliation" in report.reconciliation_html(reconciliation)
    with tempfile.TemporaryDirectory() as temp:
        path=report.generate(pipeline_profile=pipeline,feed_profile=feed,reconciliation_summary=reconciliation,path=Path(temp)/"report.html")
        html=path.read_text()
        assert "Real-Time Market Data Quality" in html and "AAPL" in html and "HEALTHY" in html
    print("All market-data quality reporting assertions passed.")
if __name__=="__main__": main()
