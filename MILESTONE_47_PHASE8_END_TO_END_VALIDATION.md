# Milestone 47 Phase 8 — End-to-End Validation and Certification

Phase 8 closes Milestone 47 with an operational certification layer that verifies the complete published-state consumption chain:

1. Alembic is at `m47_002`.
2. `current_market_state` exists and is READY or permitted DEGRADED.
3. Scanner and decision readiness flags are valid.
4. Polygon option-snapshot lineage is complete.
5. The latest scanner lineage run is READY.
6. Persisted candidate count matches the scanner-run declaration.
7. Institutional-decision lineage is available when required.
8. Historical replay is READY with zero mismatches when required.
9. Report manifests and artifact SHA-256 values are intact.

## New package

`trading_ai.certification` supplies:

- `CertificationPolicy`
- `CertificationCheck`
- `CertificationResult`
- `Milestone47CertificationService`

The service emits JSON, HTML and a checksum manifest. A failed blocking check results in process exit code 2, making the command suitable for CI/CD and startup gates.

## Certification modes

Default operational mode requires publication, scanner lineage, candidate consistency and report-manifest integrity. Decision and replay history are reported but optional.

Strict Milestone 47 certification additionally requires decision lineage and a clean historical replay.
