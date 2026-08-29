from pathlib import Path

def main():
    universe=Path('src/trading_ai/market/universe.py').read_text()
    ui=Path('ui/workstation/src/pages.tsx').read_text()
    module=Path('src/trading_ai/market/trend_universe.py').read_text()
    assert 'Strong Bullish — All Timeframes' in module
    assert 'Strong Bearish — All Timeframes' in module
    assert 'No symbols currently have STRONG_BULLISH alignment across all three trend horizons.' in module
    assert 'ORDER BY symbol, snapshot_timestamp DESC, as_of_date DESC, created_at DESC' in module
    assert 'is_trend_universe(normalized)' in universe
    assert 'trendEmptyMessage' in ui
    print('Trend universe contract assertions passed.')
if __name__=='__main__': main()
