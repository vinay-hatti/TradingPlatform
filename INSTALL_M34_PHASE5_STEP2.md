# Milestone 34 — Phase 5 — Step 2
## Pattern Discovery and Similarity Analytics

```bash
cd /Users/vinay.hatti/TradingPlatform
unzip -o m34_phase5_step2_pattern_discovery_similarity_analytics.zip -d .
```

Generate Step 1 outputs, then run:

```bash
uv run python scripts/run_m34_phase5_pattern_discovery.py \
  --knowledge-base-json reports/m34/phase5/research_knowledge_base.json \
  --output-dir reports/m34/phase5
```

Outputs:

```text
reports/m34/phase5/similar_research_cases.json
reports/m34/phase5/pattern_discovery.json
```

Tests:

```bash
uv run python scripts/test_m34_phase5_step2_similarity.py
uv run python scripts/test_m34_phase5_step2_pattern_discovery.py
uv run python scripts/test_m34_phase5_step2_governance.py
```
