# Milestone 47 Phase 7 — Historical Replay

Phase 7 adds immutable historical replay over the lineage persisted in Phase 5.

## Replay sources

A replay may be selected by:

- `scanner_run_id`
- `decision_run_id`
- `ingestion_run_id`
- `publication_name` (latest matching persisted scanner lineage)

Because `current_market_state` is a moving pointer, historical resolution is performed from the immutable lineage tables rather than from the current publication row.

## Modes

### Snapshot replay

Reconstructs the exact scanner candidates and institutional decisions stored for the selected lineage. It validates report/audit accessibility and produces deterministic canonical hashes.

### Execute replay

Accepts scanner and decision executor adapters. Recomputed outputs are canonicalized and compared with the persisted baseline. Volatile run IDs, item IDs, generation timestamps and persistence metadata are excluded from deterministic content hashing.

## Persistence

Migration `m47_002` adds:

- `historical_replay_run`
- `historical_replay_comparison`

Every replay stores its source lineage, mode, versions, result status, counts and each candidate/decision comparison.

## Reports

Each replay emits:

- `historical_replay.json`
- `historical_replay_manifest.json`

The manifest includes a SHA-256 checksum and the Phase 6 reporting context.
