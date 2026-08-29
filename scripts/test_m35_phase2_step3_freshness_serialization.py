import csv, json, tempfile
from datetime import date
from pathlib import Path
from trading_ai.scanner.market_data_quality import MarketDataCoveragePolicy, MarketDataFreshnessEngine, write_freshness_json, write_symbol_freshness_csv

def main():
    policy = MarketDataCoveragePolicy(minimum_history_days=1)
    coverage = policy.evaluate([
        policy.build_symbol_profile(symbol="AAPL", row_count=1, trading_day_count=1, earliest_date=date(2026,7,20), latest_date=date(2026,7,20))
    ])
    profile = MarketDataFreshnessEngine().evaluate(coverage, as_of_date=date(2026,7,20))
    with tempfile.TemporaryDirectory() as d:
        j = write_freshness_json(profile, Path(d)/"freshness.json")
        c = write_symbol_freshness_csv(profile, Path(d)/"freshness.csv")
        data = json.loads(j.read_text())
        assert data["fresh_symbol_count"] == 1
        rows = list(csv.DictReader(c.open()))
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["status"] == "READY"
    print("Milestone 35 Phase 2 Step 3 freshness serialization assertions passed.")

if __name__ == "__main__": main()
