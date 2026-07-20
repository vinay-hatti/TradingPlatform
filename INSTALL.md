# Milestone 34 — Phase 4 — Step 5
## Dashboard Integration, Reporting, Full Regression, and Phase Closure

## Install
```bash
cd /Users/vinay.hatti/TradingPlatform
unzip -o m34_phase4_step5_dashboard_reporting_phase_closure_v2.zip -d .
```

## One-command complete workflow
```bash
uv run python scripts/run_m34_phase4_complete_pipeline.py \
  --case-id CASE-001 \
  --symbol AAPL \
  --strategy BULL_PUT_SPREAD \
  --output-dir reports/m34/phase4
```

## Dashboard only
```bash
uv run python scripts/run_m34_phase4_dashboard.py \
  --phase4-dir reports/m34/phase4 \
  --output-dir reports/m34/phase4/dashboard
```

## Step 5 regressions
```bash
uv run python scripts/test_m34_phase4_step5_dashboard.py
uv run python scripts/test_m34_phase4_step5_dashboard_reporting.py
uv run python scripts/test_m34_phase4_phase_completion.py
```
