from pathlib import Path


def main():
    script = Path(__file__).with_name('run_market_ingestion.py').read_text()
    assert 'PolygonHistoricalProvider' in script
    assert 'Authoritative Polygon-only market ingestion pipeline' in script
    assert 'yfinance' not in script.lower()
    assert 'yahoo' not in script.lower()
    print('Milestone 46.2 authoritative Polygon provider assertions passed.')

if __name__ == '__main__': main()
