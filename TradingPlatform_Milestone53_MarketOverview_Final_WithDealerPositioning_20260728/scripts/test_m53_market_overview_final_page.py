from pathlib import Path


def main() -> None:
    pages = Path("ui/workstation/src/pages.tsx").read_text()
    app = Path("ui/workstation/src/App.tsx").read_text()
    types = Path("ui/workstation/src/types.ts").read_text()

    assert "export function MarketOverviewPage" in pages
    assert "Market overview — proposed" not in pages
    assert "COMPARISON WORKSPACE" not in pages
    assert "market-proposed" not in pages
    assert "market-proposed" not in app
    assert "market-proposed" not in types

    promoted = pages.split("export function MarketOverviewPage", 1)[1]
    required = [
        'Card title="Institutional trend breadth"',
        'Card title="Trend Intelligence"',
        'DistributionGroup title="Transition state"',
        'DistributionGroup title="Forecast direction"',
        'DistributionGroup title="Institutional participation"',
        'Card title="Sector rotation"',
        'Card title="Dealer positioning & options structure"',
        'Card title="Risk dashboard"',
    ]
    for value in required:
        assert value in promoted, value

    assert 'DistributionGroup title="Base trend"' not in promoted
    assert 'Card title="Trend operational governance"' not in promoted
    assert promoted.index('Card title="Institutional trend breadth"') < promoted.index('Card title="Trend Intelligence"')
    assert promoted.index('Card title="Sector rotation"') < promoted.index('Card title="Dealer positioning & options structure"')
    assert promoted.index('Card title="Dealer positioning & options structure"') < promoted.index('Card title="Volatility environment"')
    print("All Milestone 53 final Market Overview page assertions passed.")


if __name__ == "__main__":
    main()
