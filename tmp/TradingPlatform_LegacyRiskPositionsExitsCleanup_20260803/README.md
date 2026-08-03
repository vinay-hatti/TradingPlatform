# Legacy Risk / Positions / Exits Cleanup

This compatibility cleanup retires the artifact-backed M37/M39 workstation pages.

## UI behavior
- `#/risk`, `#/positions`, and `#/exits` redirect to `#/portfolio`.
- Risk, Positions, and Exits are removed from navigation.
- Portfolio Intelligence becomes the canonical risk/position/exit workspace.

## API compatibility
The old endpoints remain available but now read PostgreSQL-backed Portfolio Intelligence:
- `/api/v1/platform/risk`
- `/api/v1/platform/positions`
- `/api/v1/platform/exit-instructions`

They no longer read `reports/m37` or `reports/m39` files.
