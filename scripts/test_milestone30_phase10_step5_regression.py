from __future__ import annotations

from pathlib import Path
import subprocess
import sys


TESTS = (
    "test_deployment_governance.py",
    "test_release_validation_readiness.py",
    "test_deployment_automation.py",
    "test_operational_governance.py",
    "test_final_project_closure.py",
)


def main() -> None:
    scripts = Path(__file__).resolve().parent
    for name in TESTS:
        path = scripts / name
        assert path.exists(), f"Missing final regression test: {name}"
        subprocess.run([sys.executable, str(path)], check=True)

    print(
        "All Milestone 30 Phase 10 Steps 1-5 "
        "regression assertions passed."
    )


if __name__ == "__main__":
    main()
