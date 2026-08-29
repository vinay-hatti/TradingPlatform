from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TESTS = (
    "scripts/test_broker_authentication_foundation.py",
    "scripts/test_broker_contract_mapping_orders.py",
    "scripts/test_broker_order_execution_idempotency.py",
    "scripts/test_broker_status_fill_position_reconciliation.py",
    "scripts/test_broker_operational_reporting.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    missing: list[str] = []
    failed: list[tuple[str, int]] = []

    for script in TESTS:
        if not Path(script).exists():
            missing.append(script)
            print(f"[MISSING] {script}")
            continue

        print(f"[RUN] {script}")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            failed.append((script, result.returncode))

    if missing and not args.allow_missing:
        raise AssertionError(
            "Missing Milestone 30 Phase 3 tests: " + ", ".join(missing)
        )
    if failed:
        raise AssertionError(
            "Failed Milestone 30 Phase 3 tests: "
            + ", ".join(f"{script}({code})" for script, code in failed)
        )

    print("All available Milestone 30 Phase 3 regression assertions passed.")


if __name__ == "__main__":
    main()
