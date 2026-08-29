from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch the PostgreSQL-only Daily Scanner."
    )
    # Retain legacy refresh flags solely so old launchers do not fail parsing.
    # They are intentionally consumed and never forwarded or executed.
    parser.add_argument("--refresh-mode", choices=["cache_only", "refresh_missing", "force_full"], default="cache_only", help=argparse.SUPPRESS)
    parser.add_argument("--auto-refresh", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--minimum-refresh-coverage-pct", help=argparse.SUPPRESS)
    parser.add_argument("--maximum-failed-refresh-symbols", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-max-retries", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-retry-backoff-seconds", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-maximum-retry-backoff-seconds", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-retry-jitter-ratio", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-rate-limit-cooldown-seconds", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-circuit-breaker-threshold", help=argparse.SUPPRESS)
    parser.add_argument("--refresh-circuit-breaker-cooldown-seconds", help=argparse.SUPPRESS)
    parser.add_argument("--continue-on-degraded-refresh", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--block-on-degraded-refresh", action="store_true", help=argparse.SUPPRESS)
    _legacy, scanner_args = parser.parse_known_args()

    command = [sys.executable, "scripts/run_daily_scan.py", *scanner_args]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
