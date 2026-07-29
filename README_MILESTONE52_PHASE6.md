# Milestone 52 Phase 6 — Monitoring, Calibration, Drift, Attribution, Governance and Closure

## Apply
```bash
./APPLY_MILESTONE52_PHASE6.sh /Users/vinay.hatti/TradingPlatform
```

## Validate
```bash
cd /Users/vinay.hatti/TradingPlatform
uv run python scripts/test_m52_phase6_package_contract.py
uv run python scripts/test_m52_phase6_operations.py
uv run python scripts/run_trend_phase6_operations.py
uv run python scripts/test_m52_acceptance.py
```

Calibration does not invent accuracy. Until realized forecast outcomes are available, it reports `NOT_ENOUGH_HISTORY`, records the sample count, and remains non-blocking.

No database migration is required.
