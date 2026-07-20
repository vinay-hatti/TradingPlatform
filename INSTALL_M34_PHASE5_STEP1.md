# Milestone 34 — Phase 5 — Step 1
## Research Knowledge Base Foundation

## Install

```bash
cd /Users/vinay.hatti/TradingPlatform

unzip -o \
  m34_phase5_step1_research_knowledge_base_foundation.zip \
  -d .
```

## Prerequisite

Milestone 34 Phase 4 reports must exist under:

```text
reports/m34/phase4/
```

Generate them with:

```bash
uv run python \
  scripts/run_m34_phase4_complete_pipeline.py \
  --case-id CASE-001 \
  --symbol AAPL \
  --strategy BULL_PUT_SPREAD \
  --output-dir reports/m34/phase4
```

## Run Phase 5 Step 1

```bash
uv run python \
  scripts/run_m34_phase5_research_knowledge.py \
  --phase4-dir reports/m34/phase4 \
  --output-dir reports/m34/phase5 \
  --knowledge-base-id M34-PHASE5-KB-001
```

Optional additional tags:

```bash
uv run python \
  scripts/run_m34_phase5_research_knowledge.py \
  --phase4-dir reports/m34/phase4 \
  --output-dir reports/m34/phase5 \
  --knowledge-base-id M34-PHASE5-KB-001 \
  --additional-tags-json examples/m34_phase5_additional_tags.json
```

## Generated reports

```text
reports/m34/phase5/research_knowledge_base.json
reports/m34/phase5/research_index.json
```

## Tests

```bash
uv run python \
  scripts/test_m34_phase5_step1_research_knowledge.py
```

```bash
uv run python \
  scripts/test_m34_phase5_step1_knowledge_governance.py
```
