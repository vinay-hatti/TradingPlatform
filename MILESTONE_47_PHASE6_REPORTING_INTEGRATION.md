# Milestone 47 Phase 6 — Reporting Integration

Phase 6 makes scanner, live-trade, and institutional-decision exports self-describing and auditable.

## Added

- `trading_ai.reporting.ReportingContext`
- Published Market State and Governance Summary HTML blocks
- Complete scanner/candidate lineage columns in CSV
- `report_version` and `reporting_context` in JSON
- SHA-256 report manifests
- Decision JSON sidecar manifests
- Scanner version `m47.phase6.v1`

## Scanner artifacts

The daily scanner now produces:

- `recommendations.csv`
- `recommendations.json`
- `report.html`
- `report_manifest.json`
- `live_trade_candidates.csv`
- `live_trade_candidates.json`
- `live_trade_candidates.html`
- `live_trade_report_manifest.json`

## Decision artifacts

`InstitutionalDecisionService.run_and_export()` writes the requested JSON file and a sibling `<stem>_manifest.json`.

## Validation

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/test_m47_phase2_daily_scanner_published_state.py
uv run python scripts/test_m47_phase3_institutional_decision_published_state.py
uv run python scripts/test_m47_phase4_staleness_failure_governance.py
uv run python scripts/test_m47_phase5_persistent_lineage.py
uv run python scripts/test_m47_phase6_reporting_integration.py
```
