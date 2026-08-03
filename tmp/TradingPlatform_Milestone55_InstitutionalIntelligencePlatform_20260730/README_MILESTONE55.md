# Milestone 55 — Institutional Intelligence Platform

One cumulative milestone release implementing all internal phases:
1. Intelligence Framework
2. Explanation Engine
3. Recommendation Engine
4. Trade Playbook Engine
5. Opportunity Health Engine
6. Institutional Intelligence Workspace

## Apply
```bash
tar -xzf TradingPlatform_Milestone55_InstitutionalIntelligencePlatform_20260730.tar.gz -C /tmp
/tmp/TradingPlatform_Milestone55_InstitutionalIntelligencePlatform_20260730/APPLY_MILESTONE55_INSTITUTIONAL_INTELLIGENCE_PLATFORM.sh /Users/vinay.hatti/TradingPlatform
cd /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade head
PYTHONPATH=src uv run python scripts/test_m55_institutional_intelligence_platform.py
cd ui/workstation
rm -rf node_modules
npm ci
npm run typecheck
npm test
npm run build
```

Open `#/intelligence` after starting the Production API and workstation.

## API
- `POST /api/v1/institutional-intelligence/opportunities/{id}/generate`
- `GET /api/v1/institutional-intelligence/opportunities/{id}`
- `GET /api/v1/institutional-intelligence/opportunities/{id}/history`

Intelligence generation is database/snapshot based and does not trigger market or options ingestion.
