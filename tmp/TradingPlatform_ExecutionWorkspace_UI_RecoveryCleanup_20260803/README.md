# Execution Workspace UI Recovery & Legacy Cleanup

This patch makes the Milestone 59/60 database-backed OMS the only visible execution workflow.

## Fixes
- Removes the legacy **Execution** navigation item.
- Redirects `#/execution` to `#/execution-workspace`.
- Keeps old cached clients working by changing `/api/v1/platform/execution` from the M38 JSON artifact to the canonical `execution_intents` table.
- Loads the OMS queue explicitly for `PAPER-PRIMARY`.
- Adds a compatibility fallback and endpoint-specific diagnostics instead of a generic `Internal Server Error`.

No database migration is required.

After applying, restart both the backend and frontend and hard-refresh the browser.
