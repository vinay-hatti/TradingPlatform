# Install and Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone47_Phase5_PersistentLineage_20260725.tar.gz --strip-components=1
uv run alembic upgrade head
uv run alembic current
```

Expected head: `m47_001`.

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/test_m47_phase2_daily_scanner_published_state.py
uv run python scripts/test_m47_phase3_institutional_decision_published_state.py
uv run python scripts/test_m47_phase4_staleness_failure_governance.py
uv run python scripts/test_m47_phase5_persistent_lineage.py
```
