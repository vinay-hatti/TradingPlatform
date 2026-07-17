from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TESTS = (
    "scripts/test_pretrade_risk_foundation.py",
    "scripts/test_portfolio_exposure_controls.py",
    "scripts/test_options_greeks_scenario_margin.py",
    "scripts/test_trading_controls_risk_gateway_workflow.py",
    "scripts/test_risk_gateway_decision_integration.py",
    "scripts/test_risk_gateway_operational_reporting.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    missing = []
    failed = []
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
            "Missing Milestone 30 Phase 5 tests: "
            + ", ".join(missing)
        )
    if failed:
        raise AssertionError(
            "Failed Milestone 30 Phase 5 tests: "
            + ", ".join(f"{script}({code})" for script, code in failed)
        )

    print("All available Milestone 30 Phase 5 regression assertions passed.")


if __name__ == "__main__":
    main()
