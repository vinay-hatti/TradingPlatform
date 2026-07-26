# Milestone 46 NumPy Serialization Fix

Fixes PostgreSQL `schema "np" does not exist` failures caused by NumPy scalar values such as `np.float64(...)` leaking into SQL parameters.

## Changes

- Added recursive native-Python normalization in `market_intelligence/serialization.py`.
- Normalized all snapshot structures before persistence.
- Made `MarketIntelligenceSnapshot.to_dict()` JSON-safe.
- Updated the Milestone 46 CLI output serializer.
- Added `scripts/test_m46_numpy_serialization.py`.

## Validate

```bash
uv run python scripts/test_m46_numpy_serialization.py
uv run python scripts/test_m46_market_intelligence.py
uv run python scripts/test_m46_integration_contracts.py
uv run python scripts/run_m46_market_intelligence.py
```
