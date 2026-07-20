# Database Recovery Runbook

## Governance

- Runbook type: `DATABASE_RECOVERY`
- Environment: Production/Paper
- Owner: Assign accountable service owner
- Reviewer: Assign independent reviewer
- Review frequency: Quarterly
- Live trading default: Disabled

## Preconditions

1. Confirm operator identity and authorization.
2. Record incident or change identifier.
3. Confirm current environment and active release.
4. Confirm backup and rollback availability.
5. Confirm risk kill switch state.

## Procedure

1. Capture current health, readiness, metrics, and alerts.
2. Execute the approved operational action.
3. Validate market data, broker, database, risk, and execution state.
4. Reconcile orders, fills, positions, and portfolio risk.
5. Confirm audit evidence was written.
6. Escalate on any failed validation.

## Rollback / Recovery

1. Stop new order generation.
2. Activate the risk kill switch when required.
3. Restore the last validated configuration or release.
4. Reconcile persistent state.
5. Run smoke and readiness checks.
6. Obtain incident commander approval before resuming.

## Evidence

- Command transcript
- Structured logs
- Metrics snapshot
- Reconciliation report
- Approval record
- Incident/change ticket

## Completion Criteria

- All required checks pass.
- No unresolved critical or high findings.
- Audit evidence is complete.
- Service owner and reviewer sign off.
