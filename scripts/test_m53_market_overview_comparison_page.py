from pathlib import Path

def main():
    pages=Path('ui/workstation/src/pages.tsx').read_text()
    app=Path('ui/workstation/src/App.tsx').read_text()
    types=Path('ui/workstation/src/types.ts').read_text()
    styles=Path('ui/workstation/src/styles.css').read_text()
    assert 'export function MarketOverviewPage()' in pages
    assert 'export function ProposedMarketOverviewPage()' in pages
    assert "['market', 'Market overview', Globe2]" in pages
    assert "['market-proposed', 'Market overview — proposed', Globe2]" in pages
    assert 'DistributionGroup title="Base trend"' in pages, 'Current page must remain unchanged'
    proposed=pages.split('export function ProposedMarketOverviewPage()',1)[1]
    assert 'DistributionGroup title="Base trend"' not in proposed
    assert 'DistributionGroup title="Transition state"' in proposed
    assert 'DistributionGroup title="Forecast direction"' in proposed
    assert 'DistributionGroup title="Institutional participation"' in proposed
    assert 'Trend operational governance' not in proposed
    assert 'Institutional trend breadth' in proposed
    assert 'Trend watch list' in proposed
    assert "'market-proposed': ProposedMarketOverviewPage" in app
    assert "'market-proposed'" in types
    assert '.proposed-market-overview-page' in styles
    print('All Market Overview comparison-page assertions passed.')

if __name__=='__main__': main()
