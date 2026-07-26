# Milestone 47 Phase 8 — Install and Validate

## Install

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone47_Phase8_EndToEndCertification_20260725.tar.gz --strip-components=1
```

No new migration is introduced. Confirm the Phase 7 head:

```bash
uv run alembic current
uv run alembic heads
```

Expected: `m47_002`.

## Run all Milestone 47 tests

```bash
for phase in 1 2 3 4 5 6 7 8; do
  uv run python scripts/test_m47_phase${phase}_*.py
done
```

## Create a clean replay before strict certification

```bash
uv run python scripts/run_m47_historical_replay.py \
  --scanner-run-id <scanner-run-id>
```

## Strict certification

Supply the manifests produced by the latest scanner and replay runs:

```bash
uv run python scripts/run_m47_end_to_end_certification.py \
  --require-decision-lineage \
  --require-replay-history \
  --manifest reports/daily/<date>/report_manifest.json \
  --manifest reports/daily/<date>/live_trade_report_manifest.json \
  --manifest reports/m47/replay/<date>/<replay-run-id>/historical_replay_manifest.json
```

Expected status: `CERTIFIED` and exit code 0.

## Operational certification without report manifests

For database-only diagnostics:

```bash
uv run python scripts/run_m47_end_to_end_certification.py --allow-no-manifests
```

This mode is diagnostic and should not replace strict release certification.

## Output

Artifacts are written beneath:

```text
reports/m47/certification/<date>/<certification-run-id>/
```

Files:

- `milestone47_certification.json`
- `milestone47_certification.html`
- `milestone47_certification_manifest.json`
