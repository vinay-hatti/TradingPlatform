# Install and Validate Milestone 47 Phase 7

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone47_Phase7_HistoricalReplay_20260725.tar.gz --strip-components=1
uv run alembic upgrade head
uv run alembic current
```

Expected Alembic head: `m47_002`.

Run regression validation:

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/test_m47_phase2_daily_scanner_published_state.py
uv run python scripts/test_m47_phase3_institutional_decision_published_state.py
uv run python scripts/test_m47_phase4_staleness_failure_governance.py
uv run python scripts/test_m47_phase5_persistent_lineage.py
uv run python scripts/test_m47_phase6_reporting_integration.py
uv run python scripts/test_m47_phase7_historical_replay.py
```

Replay the validated scanner run:

```bash
uv run python scripts/run_m47_historical_replay.py \
  --scanner-run-id scanner-20260726T011108326684Z-b17179b3e4
```

Inspect persistence:

```sql
SELECT replay_run_id, replay_mode, source_scanner_run_id, status,
       candidate_count, decision_count, mismatch_count, completed_at
FROM historical_replay_run
ORDER BY completed_at DESC
LIMIT 10;
```
