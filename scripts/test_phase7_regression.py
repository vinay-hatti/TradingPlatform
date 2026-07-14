from pathlib import Path
import subprocess
import sys


def run(script, required=True):
    path = Path(script)
    if not path.exists():
        if required:
            raise AssertionError(f"Required regression script missing: {script}")
        print(f"SKIP: {script}")
        return
    result = subprocess.run([sys.executable, str(path)], check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def main():
    required = [
        "scripts/test_institutional_walk_forward.py",
        "scripts/test_walk_forward_adapters.py",
        "scripts/test_walk_forward_probability_calibration.py",
        "scripts/test_walk_forward_integration.py",
        "scripts/test_walk_forward_reporting.py",
        "scripts/test_walk_forward_governance.py",
        "scripts/test_walk_forward_governance_reporting.py",
    ]
    for script in required:
        run(script)
    for script in ["scripts/test_phase6_regression.py", "scripts/test_institutional_decision_engine.py"]:
        run(script, required=False)
    print("Milestone 29 Phase 7 regression assertions passed.")


if __name__ == "__main__":
    main()
