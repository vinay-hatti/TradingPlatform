# Install and validate

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone47_Phase3_InstitutionalDecisionPublishedState_20260725.tar.gz --strip-components=1
```

No migration is required.

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/test_m47_phase2_daily_scanner_published_state.py
uv run python scripts/test_m47_phase3_institutional_decision_published_state.py
uv run python scripts/test_institutional_decision_engine.py
```

Validate the active publication for decisions:

```bash
uv run python scripts/run_published_market_state.py --consumer decision
```
