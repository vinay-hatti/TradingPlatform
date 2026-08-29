from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


TESTS = [
    ("Phase 9 regression", "scripts/test_phase9_regression.py"),
    ("Adaptive strategy foundation", "scripts/test_adaptive_strategy_foundation.py"),
    ("Strategy learning and dynamic weighting", "scripts/test_strategy_learning.py"),
    ("Ensemble decision and meta-confidence", "scripts/test_ensemble_decision.py"),
    ("Online adaptation and learning-state registry", "scripts/test_online_adaptation.py"),
    ("Phase 10 Decision Engine integration", "scripts/test_phase10_decision_integration.py"),
    ("Phase 10 decision contract", "scripts/test_phase10_decision_contract.py"),
    ("Phase 10 reporting dashboard", "scripts/test_phase10_reporting.py"),
    ("Phase 10 CLI", "scripts/test_phase10_cli.py"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Milestone 29 Phase 10 regression suite")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Report missing tests without failing. Intended only for installation diagnostics.",
    )
    args = parser.parse_args()

    failures = []
    missing = []
    for label, script in TESTS:
        path = Path(script)
        if not path.exists():
            missing.append((label, script))
            print(f"[MISSING] {label}: {script}")
            continue
        print(f"[RUN] {label}: {script}")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            failures.append((label, result.returncode))

    if missing and not args.allow_missing:
        raise AssertionError("Missing Phase 10 regression tests: " + ", ".join(s for _, s in missing))
    if failures:
        raise AssertionError("Phase 10 regression failures: " + ", ".join(f"{n}={c}" for n, c in failures))

    if missing:
        print(f"Phase 10 diagnostic completed with {len(missing)} missing test(s).")
    else:
        print("All Phase 10 regression assertions passed.")


if __name__ == "__main__":
    main()
