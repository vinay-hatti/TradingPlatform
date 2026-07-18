# Milestone 32 Phase 4 — Deployment Packaging, Environment Promotion, Runtime Supervision, Backup & Recovery

## Scope

This phase adds:

- versioned deployment package creation
- release manifest and SHA-256 integrity
- governed environment promotion
- allowed promotion-path validation
- production-specific confirmation
- supervised runtime registration
- runtime start, stop, restart, and PID tracking
- restart counters and runtime logs
- backup archive creation
- backup checksum verification
- isolated restore workflow
- Deployment & Recovery workstation tab
- APIs, diagnostics, and regression tests

Live trading remains disabled by policy.

## Install

```bash
cd /Users/vinay.hatti/TradingPlatform

unzip -o \
  m32_phase4_deployment_recovery.zip \
  -d .
```

## Validate

```bash
uv run python scripts/test_ui_m32_phase4_deployment_recovery.py
```

Expected:

```text
All Milestone 32 Phase 4 Deployment Packaging, Environment Promotion, Runtime Supervision, Backup, and Recovery assertions passed.
```

## Register the workstation runtime and diagnose

```bash
uv run python scripts/diagnose_deployment_recovery.py
```

## Launch

```bash
uv run python scripts/run_ui.py
```

Open:

```text
http://127.0.0.1:8080/?view=deployment-recovery
```

Perform a hard refresh:

```text
Command + Shift + R
```

## Endpoints

```text
GET  /api/v1/deployment-recovery
POST /api/v1/deployment-recovery/packages
POST /api/v1/deployment-recovery/promotions
POST /api/v1/deployment-recovery/runtime/{name}/start
POST /api/v1/deployment-recovery/runtime/{name}/stop
POST /api/v1/deployment-recovery/runtime/{name}/restart
POST /api/v1/deployment-recovery/backups
POST /api/v1/deployment-recovery/backups/{backup_id}/verify
POST /api/v1/deployment-recovery/backups/{backup_id}/restore
```

## Artifacts

```text
reports/deployment/deployment_recovery_state.json
reports/deployment/artifacts/
reports/backups/
reports/restored/
reports/runtime/
```

Restore operations extract into an isolated recovery path rather than overwriting
the active project automatically.
