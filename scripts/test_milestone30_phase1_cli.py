from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def load_cli():
    path = Path("src/trading_ai/__main__.py")
    spec = importlib.util.spec_from_file_location("m30_phase1_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_command(module, command: str, script: str) -> None:
    with patch.object(module, "run_script") as runner:
        with patch.object(sys, "argv", ["trading_ai", command, "--sample", "1"]):
            module.main()
        runner.assert_called_once_with(script, ["--sample", "1"])


def main() -> None:
    module = load_cli()
    assert_command(
        module,
        "production-readiness-report",
        "scripts/build_production_readiness_report.py",
    )
    assert_command(
        module,
        "milestone30-phase1-regression-test",
        "scripts/test_milestone30_phase1_regression.py",
    )
    assert_command(
        module,
        "milestone30-phase1-closure-test",
        "scripts/test_milestone30_phase1_closure.py",
    )
    print("All Milestone 30 Phase 1 final CLI assertions passed.")


if __name__ == "__main__":
    main()
