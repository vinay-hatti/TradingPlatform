from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TESTS = (
    "scripts/test_canonical_order_aggregate_lifecycle.py",
    "scripts/test_order_repository_journal_audit.py",
    "scripts/test_order_routing_workflow.py",
    "scripts/test_parent_child_bracket_oco_recovery.py",
    "scripts/test_order_management_operational_reporting.py",
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
            "Missing Milestone 30 Phase 4 tests: " + ", ".join(missing)
        )
    if failed:
        raise AssertionError(
            "Failed Milestone 30 Phase 4 tests: "
            + ", ".join(f"{script}({code})" for script, code in failed)
        )

    print("All available Milestone 30 Phase 4 regression assertions passed.")


if __name__ == "__main__":
    main()
