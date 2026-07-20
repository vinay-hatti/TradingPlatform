# Milestone 34 — Phase 5 — Step 5
## Knowledge Dashboard and Phase Closure

## Install

```bash
cd /Users/vinay.hatti/TradingPlatform
unzip -o m34_phase5_step5_knowledge_dashboard_phase_closure.zip -d .
```

## Build dashboard from existing Phase 5 reports

```bash
uv run python scripts/run_m34_phase5_knowledge_dashboard.py
```

## Run complete Phase 5 reporting pipeline

```bash
uv run python scripts/run_m34_phase5_complete_pipeline.py \
  --knowledge-base-json reports/m34/phase5/research_knowledge_base.json \
  --output-dir reports/m34/phase5
```

## Outputs

```text
reports/m34/phase5/dashboard/knowledge_dashboard.html
reports/m34/phase5/dashboard/knowledge_dashboard.json
reports/m34/phase5/dashboard/knowledge_dashboard_summary.json
```

## Tests

```bash
uv run python scripts/test_m34_phase5_step5_dashboard.py
uv run python scripts/test_m34_phase5_step5_reporting.py
uv run python scripts/test_m34_phase5_milestone_completion.py
```
