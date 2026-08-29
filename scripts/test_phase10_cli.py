from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


EXPECTED = {
    "adaptive-strategy-test": "scripts/test_adaptive_strategy_foundation.py",
    "strategy-learning-test": "scripts/test_strategy_learning.py",
    "ensemble-decision-test": "scripts/test_ensemble_decision.py",
    "online-adaptation-test": "scripts/test_online_adaptation.py",
    "phase10-decision-integration-test": "scripts/test_phase10_decision_integration.py",
    "phase10-decision-contract-test": "scripts/test_phase10_decision_contract.py",
    "phase10-report-test": "scripts/test_phase10_reporting.py",
    "phase10-cli-test": "scripts/test_phase10_cli.py",
    "phase10-regression-test": "scripts/test_phase10_regression.py",
    "phase10-closure-test": "scripts/test_phase10_closure.py",
}


def load_cli():
    path = Path("src/trading_ai/__main__.py")
    if not path.exists():
        path = Path("src/trading_ai/phase10_step7___main__.py")
    assert path.exists(), "Phase 10 Step 7 CLI replacement is not installed."
    spec = importlib.util.spec_from_file_location("phase10_cli_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_cli()
    source_path = Path(module.__file__)
    source = source_path.read_text()
    for command, script in EXPECTED.items():
        assert f'sub.add_parser("{command}")' in source, command
        assert script in source, script

    for command, script in EXPECTED.items():
        captured = {}

        def fake_run(cmd):
            captured["cmd"] = cmd
            class Result:
                returncode = 0
            return Result()

        with patch.object(module.subprocess, "run", side_effect=fake_run), patch.object(
            sys, "argv", ["trading_ai", command, "--sample", "value"]
        ):
            try:
                module.main()
            except SystemExit as exc:
                assert exc.code == 0

        cmd = captured["cmd"]
        assert cmd[0] == sys.executable
        assert cmd[1] == script
        assert cmd[2:] == ["--sample", "value"]

    print("All Phase 10 CLI assertions passed.")


if __name__ == "__main__":
    main()
