# Milestone 34 — Phase 5 — Step 4
## Analyst Performance Analytics

## Install

```bash
cd /Users/vinay.hatti/TradingPlatform

unzip -o \
  m34_phase5_step4_analyst_performance_analytics.zip \
  -d .
```

## Prerequisite

Generate the Phase 5 research knowledge base:

```bash
uv run python \
  scripts/run_m34_phase5_research_knowledge.py \
  --phase4-dir reports/m34/phase4 \
  --output-dir reports/m34/phase5 \
  --knowledge-base-id M34-PHASE5-KB-001
```

## Run Step 4

```bash
uv run python \
  scripts/run_m34_phase5_analyst_performance.py \
  --knowledge-base-json reports/m34/phase5/research_knowledge_base.json \
  --output-dir reports/m34/phase5
```

## Outputs

```text
reports/m34/phase5/analyst_performance.json
reports/m34/phase5/analyst_scorecards.json
```

## Tests

```bash
uv run python scripts/test_m34_phase5_step4_analyst_performance.py
uv run python scripts/test_m34_phase5_step4_calibration.py
uv run python scripts/test_m34_phase5_step4_governance.py
```
