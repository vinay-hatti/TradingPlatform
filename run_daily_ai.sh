#!/bin/bash
set -e

echo "Running Trading AI daily workflow..."

uv run python scripts/run_dashboard.py

echo
echo "Opening dashboard..."
open reports/dashboard.html
