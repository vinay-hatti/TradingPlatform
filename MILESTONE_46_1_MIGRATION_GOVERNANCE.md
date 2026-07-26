# Milestone 46.1 — Migration Governance Cleanup

## Corrected failure

The Polygon closure revision identifier was 37 characters while the existing Alembic version table stores `version_num` as `VARCHAR(32)`. PostgreSQL therefore completed the migration DDL inside the transaction but rejected Alembic's final version-row update, causing the transaction to roll back.

The revision key is now:

```text
m46_002
```

The descriptive migration filename and docstring remain unchanged.

## Audits added

`run_migration_governance_audit.py` validates:

- every migration declares a literal revision;
- revision identifiers fit `VARCHAR(32)`;
- duplicate revisions are rejected;
- missing parents are rejected;
- cycles are rejected;
- exactly one head exists;
- explicit PostgreSQL constraint and index names fit 63 bytes;
- Milestone 46 status, provenance, strategy and outcome literals fit their schema columns.

## Recovery

The failed PostgreSQL migration was transactional, so no manual table cleanup should be necessary. Confirm the current revision remains `m46_001`, install this package, run the audit, and retry the upgrade.
