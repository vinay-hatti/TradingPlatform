#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
TARGET="$ROOT/ui/workstation/src/pages.tsx"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="$SCRIPT_DIR/payload/src/pages.tsx"
BACKUP_ROOT="$ROOT/.ui-maintenance-backups/daily-scanner-cleanup-v2"
EXPECTED_BASE="44259cc1da8a2bd3efcc9aecb5ff2c511ef63bfdec53fd825686bec6594e1d20"
EXPECTED_PATCHED="687e7754926972495df8d28606cefbb424cbe865c70b368c34c45918ab6c9fe8"

[[ -f "$TARGET" ]] || { echo "ERROR: Missing $TARGET" >&2; exit 1; }
[[ -f "$PAYLOAD" ]] || { echo "ERROR: Missing payload $PAYLOAD" >&2; exit 1; }
CURRENT="$(shasum -a 256 "$TARGET" | awk '{print $1}')"
PAYLOAD_SHA="$(shasum -a 256 "$PAYLOAD" | awk '{print $1}')"
[[ "$PAYLOAD_SHA" == "$EXPECTED_PATCHED" ]] || { echo "ERROR: Payload checksum mismatch" >&2; exit 1; }

if [[ "$CURRENT" == "$EXPECTED_PATCHED" ]]; then
  echo "Daily Scanner cleanup v2 is already applied."
  exit 0
fi
if [[ "$CURRENT" != "$EXPECTED_BASE" ]]; then
  echo "ERROR: pages.tsx does not match the uploaded post-Milestone-9 baseline." >&2
  echo "Expected: $EXPECTED_BASE" >&2
  echo "Found   : $CURRENT" >&2
  echo "No files were changed." >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$TARGET" "$BACKUP_DIR/pages.tsx"
printf '%s\n' "$BACKUP_DIR" > "$BACKUP_ROOT/LATEST"
cp "$PAYLOAD" "$TARGET"

FINAL="$(shasum -a 256 "$TARGET" | awk '{print $1}')"
[[ "$FINAL" == "$EXPECTED_PATCHED" ]] || { cp "$BACKUP_DIR/pages.tsx" "$TARGET"; echo "ERROR: Verification failed; original restored." >&2; exit 1; }

echo "Applied Daily Scanner cleanup v2."
echo "Backup: $BACKUP_DIR/pages.tsx"
echo "Changed: $TARGET"
