from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


TESTS = (
    "test_service_health_registry_foundation.py",
    "test_retry_circuit_failure_isolation.py",
    "test_recovery_restart_incident_audit.py",
    "test_watchdog_alert_escalation_integration.py",
    "test_operational_resilience_reporting_dashboard.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip unavailable earlier-step tests for installation diagnostics.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    executed = 0
    for name in TESTS:
        path = root / name
        if not path.exists():
            if args.allow_missing:
                print(f"SKIPPED missing test: {name}")
                continue
            raise FileNotFoundError(
                f"Required Milestone 30 Phase 8 test is missing: {path}"
            )
        print(f"RUNNING {name}")
        subprocess.run(
            [sys.executable, str(path)],
            check=True,
        )
        executed += 1

    if executed == 0:
        raise RuntimeError("No Milestone 30 Phase 8 tests executed.")
    print(
        "All available Milestone 30 Phase 8 regression assertions passed."
    )


if __name__ == "__main__":
    main()
