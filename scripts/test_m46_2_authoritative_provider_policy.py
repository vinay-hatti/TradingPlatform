from pathlib import Path


def main():
    script=Path(__file__).with_name('run_market_ingestion.py').read_text()
    assert 'MarketService(provider=PolygonProvider())' in script
    assert 'Yahoo OHLCV' not in script
    assert 'Polygon equities, options, and Market Intelligence' in script
    print('Milestone 46.2 authoritative Polygon provider assertions passed.')

if __name__=='__main__': main()
