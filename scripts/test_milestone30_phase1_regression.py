from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TESTS = (
    "scripts/test_production_runtime_safety.py",
    "scripts/test_environment_configuration_registry.py",
    "scripts/test_secret_governance.py",
    "scripts/test_startup_readiness_gate.py",
    "scripts/test_startup_readiness_registry_compatibility.py",
    "scripts/test_startup_readiness_cli.py",
    "scripts/test_production_readiness_reporting.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    failed = []
    missing = []

    for script in TESTS:
        path = Path(script)
        if not path.exists():
            missing.append(script)
            print(f"[MISSING] {script}")
            continue

        print(f"[RUN] {script}")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            failed.append((script, result.returncode))

    if missing and not args.allow_missing:
        raise AssertionError(
            "Missing Milestone 30 Phase 1 tests: " + ", ".join(missing)
        )
    if failed:
        raise AssertionError(
            "Failed Milestone 30 Phase 1 tests: "
            + ", ".join(f"{script}({code})" for script, code in failed)
        )

    print("All available Milestone 30 Phase 1 regression assertions passed.")


if __name__ == "__main__":
    main()
