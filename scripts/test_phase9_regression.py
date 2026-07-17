from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestTarget:
    name: str
    path: str
    required: bool = True


PHASE9_TARGETS = (
    TestTarget("Execution analytics", "scripts/test_execution_analytics.py"),
    TestTarget("Execution aggregation", "scripts/test_execution_aggregation.py"),
    TestTarget("Execution benchmark routing", "scripts/test_execution_benchmark_routing.py"),
    TestTarget("Execution Decision Engine integration", "scripts/test_execution_integration.py"),
    TestTarget("Execution reporting", "scripts/test_execution_reporting.py"),
    TestTarget("Execution governance", "scripts/test_execution_governance.py"),
    TestTarget("Execution route registry", "scripts/test_execution_route_registry.py"),
    TestTarget("Execution champion-challenger", "scripts/test_execution_champion_challenger.py"),
    TestTarget("Execution governance integration", "scripts/test_execution_governance_integration.py"),
    TestTarget("Execution governance decision contract", "scripts/test_execution_governance_decision_contract.py"),
    TestTarget("Execution governance reporting", "scripts/test_execution_governance_reporting.py"),
    TestTarget("Execution governance CLI", "scripts/test_execution_governance_cli.py"),
)


def run_target(root: Path, target: TestTarget) -> tuple[bool, str]:
    script = root / target.path
    if not script.exists():
        return False, f"MISSING: {target.path}"
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        check=False,
    )
    if completed.returncode != 0:
        return False, f"FAILED ({completed.returncode}): {target.path}"
    return True, f"PASSED: {target.path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete Milestone 29 Phase 9 regression suite.")
    parser.add_argument("--allow-missing", action="store_true", help="Skip missing scripts instead of failing.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    skipped: list[str] = []

    print("=" * 72)
    print("Milestone 29 Phase 9 — Full Regression Suite")
    print("=" * 72)

    for target in PHASE9_TARGETS:
        script = root / target.path
        if not script.exists() and args.allow_missing:
            message = f"SKIPPED: {target.path}"
            skipped.append(message)
            print(message)
            continue
        passed, message = run_target(root, target)
        print(message)
        if not passed:
            failures.append(message)

    print("-" * 72)
    print(f"Total targets : {len(PHASE9_TARGETS)}")
    print(f"Passed        : {len(PHASE9_TARGETS) - len(failures) - len(skipped)}")
    print(f"Skipped       : {len(skipped)}")
    print(f"Failed        : {len(failures)}")

    if failures:
        raise SystemExit("Phase 9 regression failed:\n" + "\n".join(failures))

    print("All available Phase 9 regression assertions passed.")


if __name__ == "__main__":
    main()
