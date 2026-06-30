#!/bin/bash
set -e

uv run python scripts/run_dashboard.py

open reports/dashboard.html
