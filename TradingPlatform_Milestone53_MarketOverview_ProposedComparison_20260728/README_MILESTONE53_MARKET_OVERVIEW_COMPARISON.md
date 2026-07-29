# Milestone 53 — Proposed Market Overview Comparison Page

This cumulative drop-in package preserves the existing **Market overview** page and adds a separate **Market overview — proposed** page at `#/market-proposed`.

## Comparison design

- Existing `#/market` page remains unchanged.
- New decision-first page uses the same `/api/v1/market-overview/latest` snapshot.
- Navigation exposes both pages for direct comparison.
- The proposed layout includes:
  - market posture summary
  - market health and regime context
  - institutional trend breadth before Trend Intelligence
  - Trend Intelligence without Base Trend distribution
  - three visual distributions: Transition, Forecast, Institutional Participation
  - combined three-column Trend Watch List
  - sector rotation
  - volatility, liquidity, and opportunity context
  - risk dashboard
  - cross-asset confirmation and freshness

## Apply

```bash
unzip TradingPlatform_Milestone53_MarketOverview_ProposedComparison_20260728.zip
cd TradingPlatform_Milestone53_MarketOverview_ProposedComparison_20260728
./APPLY_MILESTONE53_MARKET_OVERVIEW_COMPARISON.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
uv run python scripts/test_m53_market_overview_comparison_page.py
uv run python scripts/test_m53_ui_contract.py
cd ui/workstation
npm run build
```

Open both:

- Current: `#/market`
- Proposed: `#/market-proposed`
