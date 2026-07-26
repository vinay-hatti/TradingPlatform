# Milestone 46 — Polygon Authoritative Closure

This continuation uses Polygon as the sole authoritative raw market-data provider.

## AC-6
Adds `option_snapshot_run` and `option_contract_snapshot`, preserving multiple same-day captures with snapshot-level idempotency. Bid/ask and Greeks remain nullable and quote quality is explicit.

## AC-8
Adds governed historical IV rank, IV percentile, realized volatility, volatility-risk-premium support, strategy-fit classification and `underlying_volatility_snapshot`. Calculations reject insufficient history rather than manufacturing confidence.

## AC-9
Adds Polygon trade and NBBO quote event tables and microstructure liquidity snapshots. Spread, executable quote coverage and average trade size are computed. Full depth is explicitly `CAPABILITY_UNAVAILABLE`.

## AC-14
Adds typed `InstitutionalMarketContext`, strategy-aware `InstitutionalMarketIntelligencePolicy`, explainable score decomposition, neutral missing-data fallback and direct Institutional Decision Engine integration.

## Install

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf TradingPlatform_Milestone46_PolygonAuthoritativeClosure_20260725.tar.gz --strip-components=1
uv run alembic upgrade head
uv run python scripts/test_m46_polygon_closure.py
```
