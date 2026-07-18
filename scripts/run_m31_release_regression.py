from __future__ import annotations

import subprocess
import sys


TESTS = [
    "scripts/test_ui_phase5_portfolio_risk.py",
    "scripts/test_ui_phase6_execution_console.py",
    "scripts/test_ui_phase7_reporting_audit.py",
    "scripts/test_ui_phase8_admin_runtime.py",
    "scripts/test_ui_phase9_auth_session.py",
    "scripts/test_ui_phase10_workstation_release.py",
]


def main():
    failures = []
    for test in TESTS:
        print(f"\n=== Running {test} ===")
        result = subprocess.run(
            [sys.executable, test],
            check=False,
        )
        if result.returncode != 0:
            failures.append(test)

    if failures:
        print("\nMilestone 31 release regression failed:")
        for test in failures:
            print(f"- {test}")
        raise SystemExit(1)

    print("\nAll Milestone 31 release regression tests passed.")


if __name__ == "__main__":
    main()
