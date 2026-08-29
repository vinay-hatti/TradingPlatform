#!/bin/bash
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
shift || true

cd "$PROJECT_DIR"
echo "M68.2.1.8 manual ingestion: underlying stage"
if uv run python scripts/ingest_underlying_data.py "$@"; then
  underlying_exit=0
else
  underlying_exit=$?
  echo "FAILED: underlying ingestion exit=$underlying_exit; options stage not started" >&2
  exit "$underlying_exit"
fi

echo "M68.2.1.8 manual ingestion: options stage"
if uv run python scripts/ingest_options_data.py "$@"; then
  options_exit=0
else
  options_exit=$?
  echo "FAILED: options ingestion exit=$options_exit" >&2
  exit "$options_exit"
fi

echo "M68.2.1.8 manual ingestion cycle PASSED"
