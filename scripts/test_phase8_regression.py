import subprocess
import sys
from pathlib import Path


def run(script, required=True):
    path = Path(script)
    if not path.exists():
        if required:
            raise AssertionError(f"Required regression script missing: {script}")
        return
    result = subprocess.run([sys.executable, str(path)], check=False)
    assert result.returncode == 0, f"Regression failed: {script}"


def main():
    required = [
        "scripts/test_market_regime_engine.py",
        "scripts/test_market_regime_forecast.py",
        "scripts/test_market_breadth_engine.py",
        "scripts/test_market_regime_integration.py",
        "scripts/test_market_regime_reporting.py",
        "scripts/test_market_regime_governance.py",
        "scripts/test_market_regime_governance_reporting.py",
    ]
    for script in required:
        run(script)
    run("scripts/test_phase7_regression.py", required=False)
    print("Milestone 29 Phase 8 regression assertions passed.")


if __name__ == "__main__":
    main()
