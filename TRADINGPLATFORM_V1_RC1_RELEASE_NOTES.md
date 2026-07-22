# TradingPlatform v1.0 RC1

This release candidate synchronizes Milestones 36 through 42 on top of the uploaded TradingPlatform repository.

## Stabilization fixes

- Corrected the Milestone 42 workstation launcher to use the Milestone 41 `mount_workstation(app, *, repository_root=...)` contract.
- Corrected reload startup so `scripts/` does not need to be a Python package.
- Preserved the Milestone 41 TypeScript configuration and strict-mode source fixes.
- Preserved the Milestone 41 direct FastAPI-object launcher fix.
- Verified the production API and real-time router can be imported without circular imports.
- Verified a single Alembic head: `m42ops`.
- Added `scripts/validate_v1_rc1.py` for repeatable cross-milestone validation.

## Validation summary

- Python compilation: passed.
- Milestone 36-42 regression scripts: 51 passed.
- Milestone 36-42 CLI help/import checks: passed.
- Production API route generation: 19 routes, passed.
- Alembic graph: 12 revisions, one head (`m42ops`), passed.
- Frontend Node utility tests: passed.
- Frontend TypeScript/Vite compilation requires `npm install` in the target repository; registry access was unavailable in the packaging environment.

## Start the stabilized command center

```bash
uv sync
uv run alembic upgrade head
cd ui/workstation
npm install
npm run typecheck
npm run test
npm run build
cd ../..
uv run python scripts/run_m42_command_center.py --host 127.0.0.1 --port 8000
```

## Full validation

```bash
uv run python scripts/validate_v1_rc1.py
```
