# Milestone 34 — Phase 5 — Step 3
## Institutional Learning Engine

Install:
```bash
cd /Users/vinay.hatti/TradingPlatform
unzip -o m34_phase5_step3_institutional_learning_engine.zip -d .
```

Run:
```bash
uv run python scripts/run_m34_phase5_institutional_learning.py --knowledge-base-json reports/m34/phase5/research_knowledge_base.json --output-dir reports/m34/phase5
```

Outputs:
- `reports/m34/phase5/institutional_learning.json`
- `reports/m34/phase5/learning_summary.json`

Tests:
```bash
uv run python scripts/test_m34_phase5_step3_learning.py
uv run python scripts/test_m34_phase5_step3_strategy_learning.py
uv run python scripts/test_m34_phase5_step3_governance.py
```
