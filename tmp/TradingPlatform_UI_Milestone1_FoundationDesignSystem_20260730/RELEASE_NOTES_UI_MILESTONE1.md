# Release Notes

## Compatibility
- No backend changes.
- No database migration.
- No route removals.
- No API contract changes.
- Existing page components remain mounted through the new shell.

## Operational notes
The Global Intelligence Header reads existing `/api/v1/platform/overview` and `/api/v1/platform/readiness` endpoints. If unavailable, the shell remains usable and displays an offline/unknown context rather than blocking navigation.
