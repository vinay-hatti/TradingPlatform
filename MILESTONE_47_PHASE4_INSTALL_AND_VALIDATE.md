# Install and validate Milestone 47 Phase 4

Install over Phase 3, then run:

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/test_m47_phase2_daily_scanner_published_state.py
uv run python scripts/test_m47_phase3_institutional_decision_published_state.py
uv run python scripts/test_m47_phase4_staleness_failure_governance.py
```

Validate the current scanner publication:

```bash
uv run python scripts/run_published_market_state.py --consumer scanner
```

Override warning and hard-stale thresholds when required:

```bash
uv run python scripts/run_published_market_state.py \
  --consumer scanner \
  --warning-age-hours 12 \
  --maximum-age-hours 18
```
