#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
LATEST="$(ls -dt "$TARGET"/backups/m54_phase2_* 2>/dev/null | head -n 1 || true)"
[ -n "$LATEST" ] || { echo "No Milestone 54 Phase 2 backup found."; exit 1; }
bash "$LATEST/ROLLBACK.sh"
echo "Rolled back using $LATEST"
